"""Define various helper functions."""

import datetime
import importlib

# Proxy for datetime.now() so that it can be stubbed while testing.
now = datetime.datetime.now


def class_from_path(path: str):
    """Import a class using its qualified name."""
    module_path, class_name = path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)
