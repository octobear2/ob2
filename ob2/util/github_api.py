import github3

import ob2.config as config


def _get_github_admin():
    return github3.login(token=config.github_admin_access_token)


def get_branch_hash(repo_name, branch_name="master"):
    """
    Retrieves the commit hash of a branch.

    """
    github = _get_github_admin()
    try:
        repository = github.repository(config.github_organization, repo_name)
        return repository.branch(branch_name).commit.sha
    except AttributeError:
        pass


def get_commit_message(repo_name, commit_hash):
    """
    Retrieves a commit message, given a repository name and a commit hash. The commit hash should
    be the unabbreviated hash.

    """
    github = _get_github_admin()
    try:
        repository = github.repository(config.github_organization, repo_name)
        return repository.git_commit(commit_hash).message
    except AttributeError:
        pass


def get_diff_file_list(repo_name, base_hash, head_hash):
    """
    Gets a list of files that have changed between base_hash..head_hash in the particular repo.

    """
    github = _get_github_admin()
    try:
        repository = github.repository(config.github_organization, repo_name)
        comparison = repository.compare_commits(base_hash, head_hash)
        file_list = [file_["filename"] for file_ in comparison.files]
        return file_list
    except AttributeError:
        pass


def download_archive(repo_name, ref, output_file, file_format="tarball"):
    """
    Downloads a repository to a local directory. Returns whether the download was successful.

    """
    github = _get_github_admin()
    repository = github.repository(config.github_organization, repo_name)
    if repository is None:
        return False
    return repository.archive(file_format, output_file, ref)


def _assign_repo(repo_name, members=[]):
    """
    (PRIVATE method, use the repomanager instead) Creates the repository and adds the members as
    contributors, idempotently.

    """
    if config.github_read_only_mode:
        raise RuntimeError("Cannot assign repo because of GitHub read-only mode")
    github = _get_github_admin()
    fq_repo_name = "%s/%s" % (config.github_organization, repo_name)
    organization = github.organization(config.github_organization)
    try:
        repo = organization.create_repo(repo_name, private=config.github_private_repos)
    except github3.GitHubError as e:
        if e.args and hasattr(e.args[0], "status_code") and e.args[0].status_code == 422:
            repo = github.repository(config.github_organization, repo_name)
            assert repo, "Unable to get repository object for GitHub (check API key permissions?)"
        else:
            raise

    collaborators = {user.login for user in repo.iter_collaborators()}

    for member in members:
        if member not in collaborators:
            successfully_added = repo.add_collaborator(member)
            assert successfully_added, "Unable to add member %s to %s" % (repr(member),
                                                                          repr(fq_repo_name))


class GitHubTransactionError(Exception):
    pass
