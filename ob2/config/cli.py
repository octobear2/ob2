import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-C", "--config", action="append", default=[],
                        help="Extra configuration directories")
    parser.add_argument("-I", "--ipython", action="store_true", default=False,
                        help="Start an IPython shell instead of the server.")
    args = parser.parse_args()
    return args
