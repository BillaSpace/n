import os
import glob
from os.path import isfile, dirname

def __list_all_modules():
    work_dir = dirname(__file__)
    mod_paths = glob.glob(os.path.join(work_dir, "**", "*.py"), recursive=True)

    all_modules = []
    for path in mod_paths:
        if isfile(path) and not path.endswith("__init__.py"):
            # Convert file path to dot notation
            rel_path = os.path.relpath(path, work_dir).replace(os.sep, ".")
            module_path = rel_path[:-3]  # remove .py extension
            all_modules.append(module_path)

    return all_modules

ALL_MODULES = sorted(__list_all_modules())
__all__ = ALL_MODULES + ["ALL_MODULES"]
