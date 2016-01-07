# Set up logging, as early as possible.
import logging
root_logger = logging.getLogger()
formatter = logging.Formatter("%(levelname)-.1s[%(asctime)s][%(name)s] %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Validates presence of required packages and package version numbers
# This must run before anything else.
from ob2.util.vendor_data import validate_packages
validate_packages()

__all__ = []
