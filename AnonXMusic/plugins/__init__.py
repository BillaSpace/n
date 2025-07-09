import os
import glob
from os.path import isfile, dirname

def __list_all_modules():
    work_dir = dirname(__file__)
    mod_paths = glob.glob(work_dir + "/**/*.py", recursive=True)

    all_modules = []
    for f in mod_paths:
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py"):
            rel_path = os.path.relpath(f, work_dir).replace(os.sep, ".")[:-3]
            all_modules.append(rel_path)

    return all_modules

ALL_MODULES = sorted(__list_all_modules())
__all__ = ALL_MODULES + ["ALL_MODULES"]
