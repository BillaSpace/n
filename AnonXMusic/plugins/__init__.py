import glob
import os
from os.path import dirname, isfile


def __list_all_modules():
    work_dir = dirname(__file__)
    mod_paths = glob.glob(os.path.join(work_dir, "*", "*.py"))

    all_modules = [
        os.path.relpath(f, work_dir).replace(os.sep, ".")[:-3]
        for f in mod_paths
        if isfile(f) and f.endswith(".py") and not f.endswith("__init__.py")
    ]

    return all_modules


ALL_MODULES = sorted(__list_all_modules())
__all__ = ALL_MODULES + ["ALL_MODULES"]
