import re
from glob import glob

import ob2.config as config
from ob2.util.hooks import apply_filters, get_job

_assignment_by_name = None


def get_assignment_by_name(name, default=None):
    global _assignment_by_name
    if _assignment_by_name is None:
        _assignment_by_name = {assignment.name: assignment
                               for assignment in config.assignments}
    return _assignment_by_name[name]


def get_repo_type(repo_name):
    """
    Returns either "group" or "personal", depending on what repo_name appears to be. If repo is
    unidentifiable, return None.

    """
    if re.match(r'^group\d+$', repo_name):
        repo_type = "group"
    elif re.match(r'^[a-z]{2,3}$', repo_name):
        repo_type = "personal"
    else:
        repo_type = None

    # This is a useful hook to change how repos are classified, based on their name. The default is
    # pretty good, but you may have extra repos that don't exactly follow this naming scheme.
    #
    # Arguments:
    #   repo_type -- The original guess for the repo_type (see code above)
    #   repo_name -- The name of the repo (e.g. "aa" or "group1")
    #
    # Returns:
    #   Either "group" or "personal"
    repo_type = apply_filters("get-repo-type", repo_type, repo_name)

    return repo_type


def _validate_apparmor_config(profile_name):
    profile_name_paths = glob("/sys/kernel/security/apparmor/policy/profiles/*/name")
    for path in profile_name_paths:
        with open(path) as f:
            if f.read().strip() == profile_name:
                break
    else:
        assert 0, ("I can't find an apparmor profile named %s\n"
                   "If this is a development environment, the VM provisioner should have set up "
                   "the 'ob2docker' apparmor profile for you.\n"
                   "Check out /sys/kernel/security/apparmor/policy/profiles/*/name for available "
                   "profiles.") % repr(profile_name)


def validate_config():
    if config.inst_account_enabled:
        assert config.mailer_enabled, \
            "The inst account forms plugin will not work without the mailer"
        assert config.inst_account_forms_path, \
            "The inst account forms plugin requires inst_account_forms_path"

    if config.groups_enabled:
        assert 1 <= config.group_min_size <= config.group_max_size
    else:
        assert not any([assignment.is_group for assignment in config.assignments]), \
            "Group assignments will not work if groups are not enabled."

    if config.dockergrader_apparmor_profile:
        _validate_apparmor_config(config.dockergrader_apparmor_profile)

    for assignment in config.assignments:
        if not assignment.manual_grading:
            assert get_job(assignment.name), "No job found for %s" % assignment.name

    for array_key in ["github_ta_usernames",
                      "github_webhook_secrets"]:
        assert not isinstance(getattr(config, array_key), basestring)

    # The port number should be ommitted if it is the default HTTP/HTTPS port.
    assert not config.web_public_host.endswith(":80")
    assert not config.web_public_host.endswith(":443")


    assert not config.web_public_root == "/", "Set web_public_root to empty string instead."
    assert config.web_public_root == "" or config.web_public_root.startswith("/"), \
            "If the web_public_root is not empty, always include the leading slash."
    assert not config.web_public_root.endswith("/"), "Remove trailing slash from web_public_root"

    assert len(set([a.name for a in config.assignments])) == len(config.assignments)
