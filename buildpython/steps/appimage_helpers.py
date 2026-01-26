from __future__ import annotations

"""Compatibility re-exports for AppImage build helpers.

Historically, the AppImage step imported helpers from this single module.
It is now split into focused modules under `buildpython.steps.appimage`.

Keep this facade stable to avoid churn in `step_appimage.py` and any external
scripts that import these helpers.
"""

from .appimage.appindicator_bundle import bundle_libappindicator
from .appimage.common import chmod_x, download, env_flag, run_checked, write_text
from .appimage.pygobject_bundle import bundle_pygobject
from .appimage.python_runtime import bundle_python_runtime
from .appimage.tkinter_bundle import bundle_tkinter

__all__ = [
    "bundle_libappindicator",
    "bundle_pygobject",
    "bundle_python_runtime",
    "bundle_tkinter",
    "chmod_x",
    "download",
    "env_flag",
    "run_checked",
    "write_text",
]
