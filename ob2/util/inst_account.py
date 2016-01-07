import ob2.config as config
from os.path import exists, join


def get_inst_account_form_path(login):
    """
    Returns the path to the PDF file that contains the account form for user with login.

    login -- The instructional account login without any prefix (e.g. aa)

    """

    if not config.inst_account_enabled:
        raise RuntimeError("Tried to get instructional account form path when account forms are "
                           "disabled")
    path = join(config.inst_account_forms_path, "%s.pdf" % login)
    if not exists(path):
        raise ValueError("No such account form with login: %s" % login)
    return path
