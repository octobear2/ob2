import sys


def validate_packages():
    """
    Performs basic validation of Python and installed Python packages. This is a useful place to
    check version numbers (for known bad packages) and to provide nicer error messages instead of
    import errors.

    """
    assert sys.version_info[:2] == (2, 7), "Please use Python 2.7"

    try:
        import apsw
    except ImportError:
        raise RuntimeError("The APSW library for SQLite is missing.\n"
                           "Please install the APSW library.\n"
                           "You can use the bundled './build_apsw.sh' script to do this.")

    assert apsw.SQLITE_VERSION_NUMBER >= 3008010, "Please use an updated library of APSW/SQLite."
