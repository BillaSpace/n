import os
from os.path import isfile, join

def __list_all_modules():
    plugin_dir = os.path.dirname(__file__)
    all_modules = [
        f[:-3]
        for f in os.listdir(plugin_dir)
        if isfile(join(plugin_dir, f)) and f.endswith(".py") and f != "__init__.py"
    ]
    return all_modules

ALL_MODULES = sorted(__list_all_modules())
__all__ = ALL_MODULES + ["ALL_MODULES"]
