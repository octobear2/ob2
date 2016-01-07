import logging
import os
import sys
import yaml
from os.path import abspath, dirname, exists, join

from ob2.config.assignment import Assignment
from ob2.config.cli import parse_args

LOG = logging.getLogger(__name__)


class _ConfigModule(object):
    def __init__(self, mode):
        # A dictionary of configuration values.
        self._config = {}

        # Should be "server" or "ipython"
        self.mode = mode

        # A list of "functions.py" files that will be executed after the configuration values and
        # the runtime system have finished loading, but before the services are started. These files
        # can contain hooks (see ob2/util/hooks.py) and other code to run.
        self._custom_functions_files = []

    def exec_custom_functions(self):
        for f in self._custom_functions_files:
            execfile(f, {"__file__": f})

    def _load_from_directory(self, directory):
        """
        Loads configuration from DIRECTORY. The directory can have:

          config.yaml  -- Contains key-value pairs
          functions.py -- Contains arbitrary Python code (useful for registering hooks)

        """
        LOG.info("Loading configuration from %s" % repr(abspath(directory)))

        try:
            with open(join(directory, "config.yaml")) as f:
                config_dict = yaml.load(f.read())
        except IOError:
            LOG.info("  -> No config.yaml found (skipping)")
        else:
            for key, value in config_dict.items():
                # We support the special suffixes "_APPEND" and "_UPDATE" for advanced users who
                # need to modify (rather than replace) a configuration value.
                is_append = is_update = False
                if key.endswith("_APPEND"):
                    key = key[:-len("_APPEND")]
                    is_append = True
                elif key.endswith("_UPDATE"):
                    key = key[:-len("_UPDATE")]
                    is_update = True

                if key == "assignments":
                    # The "assignments" dictionary is special. We turn the assignments into objects
                    # first, because they're so important and so often used.
                    assert isinstance(value, list)
                    value = [Assignment(**kwargs) for kwargs in value]
                elif key.endswith("_path"):
                    # Configuration options that end in "_path" are treated specially.
                    # Paths are relative to the config directory root.
                    assert isinstance(value, basestring)
                    value = abspath(join(directory, value))

                if is_append:
                    assert isinstance(value, list)
                    if key in self._config:
                        assert isinstance(self._config[key], list)
                        self._config[key].extend(value)
                    else:
                        self._config[key] = value
                elif is_update:
                    assert isinstance(value, dict)
                    assert key not in self._config or isinstance(self._config[key], dict)
                else:
                    self._config[key] = value
            LOG.info("  -> config.yaml loaded")

        # Supports an optional "functions.py" script, which can register hooks.
        functions_script = join(directory, "functions.py")
        if exists(functions_script):
            self._custom_functions_files.append(functions_script)
            LOG.info("  -> functions.py loaded")
        else:
            LOG.info("  -> No functions.py found (skipping)")

    def _lookup(self, key):
        try:
            return self._config[key]
        except KeyError:
            raise KeyError("No such configuration key: %s" % repr(key))

    def __getattr__(self, key):
        return self._lookup(key)


args = parse_args()
config_mode = "ipython" if args.ipython else "server"
config_module = _ConfigModule(mode=config_mode)

# Step 1: Load from the defaults that are bundled with ob2
config_module._load_from_directory(join(dirname(__file__), "..", "..", "config"))

# Step 2: Load from paths in OB2_CONFIG_PATHS environment variable, if any
for directory in os.environ.get("OB2_CONFIG_PATHS", "").split(":"):
    directory = directory.strip()
    if directory:
        config_module._load_from_directory(directory)

# Step 3: Load from paths specified on the command line, if any
for directory in args.config:
    config_module._load_from_directory(directory)

sys.modules[__name__] = config_module
