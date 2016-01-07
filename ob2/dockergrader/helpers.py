import errno
import logging
import re
import shutil
from contextlib import contextmanager
from tempfile import mkdtemp

import ob2.util.github_api as github_api
from ob2.dockergrader.job import JobFailedError


@contextmanager
def get_working_directory():
    """
    Creates a temporary directory and deletes it when finished. You should probably wrap your
    autograder script within one of these things:

    with get_working_directory() as wd:
        do_stuff_with(wd)
        ...etc...

    """
    try:
        directory = mkdtemp()
        yield directory
    finally:
        try:
            shutil.rmtree(directory)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


def download_repository(*args, **kwargs):
    """
    Downloads a repository to a local directory. Raises JobFailedError if the download was not
    successful.

    """
    if not github_api.download_archive(*args, **kwargs):
        raise JobFailedError("I tried to download your code from GitHub, but was unable to do " +
                             "so. This might be caused by a temporary problem with my " +
                             "connection to GitHub, or it might be caused by a misconfiguration " +
                             "of the build script.", critical=True)


def extract_repository(container, archive_path, destination_path, user=None):
    """
    Extracts a repository in the directory that it's located in. Optionally changes ownership of
    the extracted repository to USER.

    """
    result = container.bash("""if [[ -f {0} ]]; then
                                   mkdir -p {1} &>/dev/null
                                   tar -xf {0} -C {1} --strip-components=1 &>/dev/null
                                   if [[ $? = 0 ]]; then
                                       echo -n "pass"
                                   fi
                               fi
                            """.format(bash_quote(archive_path), bash_quote(destination_path)))
    if result != "pass":
        raise JobFailedError("I tried to extract your code from GitHub, but was unable to do " +
                             "so. Someone should probably investigate this.")
    if user:
        take_ownership(container, destination_path, user)


def take_ownership(container, path, user, group=None):
    if group is None:
        group = user
    result = container.bash("""chown -R %s:%s -- %s &>/dev/null
                               if [[ $? = 0 ]]; then
                                   echo -n "pass"
                               fi
                            """ % (bash_quote(user), bash_quote(group), bash_quote(path)))
    if result != "pass":
        raise JobFailedError("I tried taking ownership of this directory, but it didn't work. " +
                             "This probably means there's a programming error.")


def ensure_no_binaries(container, path, whitelist=[]):
    # This command should NOT follow symbolic links.
    ignores = " ".join(["! -path %s"] * len(whitelist)) % map(bash_quote, whitelist)
    find_payload = 'file -i "$0" | egrep -q "x-(sharedlib|object|executable); charset=binary"'
    result = container.bash(r"""cd %s
                                find . -type f ! -empty %s -exec sh -c %s {} \; -print
                             """ % (bash_quote(path), ignores, bash_quote(find_payload)))
    binaries = result.strip()
    if binaries:
        raise JobFailedError("I found some binary files in your code. Please remove the " +
                             "following files before we continue:\n\n" + binaries)


def ensure_files_exist(container, path, files):
    """
    Ensures that each element of FILES is a file inside the container's filesystem relative to PATH.
    This does not work for directories (by design). Files should be in the form `./path/file.c`.

    """
    file_paths = container.bash("cd %s ; find . -type f -print0" % bash_quote(path))
    files = set(files)
    for file_path in file_paths.split("\0"):
        if file_path:
            # There's a trailing null-byte at the end of the output (probably?)
            files.discard(file_path)
    if files:
        raise JobFailedError("All of the following files are REQUIRED to be present in your " +
                             "code, but I didn't find some of them. Please verify that each " +
                             "of the files exists:\n\n" + "\n".join(sorted(files)))


def ensure_files_match(container, path, file_checksums):
    """
    Ensures that files have not been tampered with. Uses SHASUM in text mode (default).

        PATH           -- The path to search.
        FILE_CHECKSUMS -- A list of (sha1sum, file_path) pairs. The file_path should be in the form
                          `./path/file.c`.

    """
    actual_sums = {}
    actual_sum_bytes = container.bash("cd %s ; find . -type f -print0 | xargs -0 sha1sum" %
                                      bash_quote(path))
    actual_sum_line_matcher = re.compile(r"^(?P<checksum>[\da-fA-F]+)[ \t](?P<mode>[ *?^])" +
                                         r"(?P<name>[^\0]*)")
    for actual_sum_line in actual_sum_bytes.split("\n"):
        if not actual_sum_line:
            continue
        if actual_sum_line[0] == "\\":
            # Special syntax in Ubuntu sha1sum for escaping the newline character in a file name
            # This code is adapted from unescape() in /usr/bin/shasum
            actual_sum_line = actual_sum_line[1:]
            actual_sum_line = actual_sum_line.replace("\\\\", "\0")
            actual_sum_line = actual_sum_line.replace("\\n", "\n")
            actual_sum_line = actual_sum_line.replace("\0", "\\")
        match = actual_sum_line_matcher.match(actual_sum_line)
        if not match:
            raise JobFailedError("Invalid line in file checksum output. (Probably a bug in the " +
                                 "autograder?")
        if match.group("mode") != " ":
            raise JobFailedError("Mode not 'text' in the file checksum output. (Probably a bug " +
                                 "in the autograder?")
        name = match.group("name")
        checksum = match.group("checksum")
        actual_sums[name] = checksum

    missing_checksums = []
    mismatched_checksums = []
    for expected_sum, file_path in file_checksums:
        if file_path not in actual_sums:
            missing_checksums.append(file_path)
        elif expected_sum != actual_sums[file_path]:
            mismatched_checksums.append(file_path)

    message = ""
    if mismatched_checksums:
        message += ("The following files must NOT be modified. Please replace them with fresh " +
                    "copies from the staff skeleton code:\n\n")
        message += "".join(["    %s\n" % file_path for file_path in mismatched_checksums])
    if missing_checksums:
        if mismatched_checksums:
            # If both types of messages are present, then space it out a little
            message += "\n"
        message += ("The following files must NOT be modified. I tried comparing their contents " +
                    "with the original skeleton code, but I could not find these files in your " +
                    "code. Please make sure these files are present and unmodified:\n\n")
        message += "".join(["    %s\n" % file_path for file_path in missing_checksums])
    if message:
        raise JobFailedError(message)


def copy(source, destination):
    """
    Copy files.

    """
    shutil.copy(source, destination)


def copytree(source, destination, symlinks=True):
    """
    Copy recursively.

    """
    shutil.copytree(source, destination, symlinks=symlinks)


def safe_get_results(output_file_path, score_file_path):
    """
    Safely tries to retrieve results from a stdout file and a score file. If anything is wrong
    (missing file, invalid score, etc.), we will just raise JobFailedError.

    """
    output = None
    try:
        with open(output_file_path) as output_file, \
                open(score_file_path) as score_file:
            output = output_file.read(512*1024)
            score = score_file.read(128)
            score = float(score)
            return output, score
    except:
        logging.exception("safe_get_results(): failed due to exception")
        if output is not None:
            logging.critical(output)
        raise JobFailedError("There was a failure in the internals of the autograder. Notify " +
                             "your TA, and maybe I will get fixed.")


def bash_quote(s):
    """
    POSIX-compatible argument escape function designed for bash. Use this to quote variable
    arguments that you send to `container.bash("...")`.

    Note that pipes.quote and subprocess.list2cmdline both produce the INCORRECT value to use in
    this scenario. Do not use those. Use this.

    Example:

        container.bash("ls -ahl %s" % bash_quote(file_name))

    """

    return "'" + s.replace("'", "'\\''") + "'"
