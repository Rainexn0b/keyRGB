"""Keyboard layout catalog and resolution helpers.

Usage
-----
from src.core.resources.layouts import LAYOUT_CATALOG, get_layout_keys, resolve_layout_id

# All available layouts for a UI dropdown:
for ld in LAYOUT_CATALOG:
    print(ld.layout_id, ld.label)

# Keys for a specific layout (or "auto"):
keys = get_layout_keys("iso")
"""

from .catalog import LAYOUT_CATALOG
from ._defs import LayoutDef
from ._api import clear_layout_cache, get_layout_keys, resolve_layout_id

__all__ = [
    "LAYOUT_CATALOG",
    "LayoutDef",
    "clear_layout_cache",
    "get_layout_keys",
    "resolve_layout_id",
]
