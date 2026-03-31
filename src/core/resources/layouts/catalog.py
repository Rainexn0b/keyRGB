"""Built-in keyboard layout catalog.

Each ``LayoutDef`` entry describes one physical keyboard variant that KeyRGB
can display in its per-key editor and calibrator.  The list order is the order
shown in UI dropdowns.

Layout IDs follow the Linux kernel / ISO naming conventions where practical.
Users pick a layout once; it is stored in ``config.physical_layout``.
``"auto"`` is a synthetic entry that triggers runtime sysfs detection.
"""

from __future__ import annotations

from ._defs import LayoutDef

# ------------------------------------------------------------------ catalog --

LAYOUT_CATALOG: list[LayoutDef] = [
    LayoutDef(
        layout_id="auto",
        label="Auto-detect",
    ),
    LayoutDef(
        layout_id="ansi",
        label="ANSI (101/104-key)",
    ),
    LayoutDef(
        layout_id="iso",
        label="ISO (102/105-key)",
    ),
    LayoutDef(
        layout_id="ks",
        label="KS (103/106-key)",
    ),
    LayoutDef(
        layout_id="abnt",
        label="ABNT (104/107-key)",
    ),
    LayoutDef(
        layout_id="jis",
        label="JIS (106/109-key)",
    ),
]

# Fast lookup by layout_id.
_LAYOUT_BY_ID: dict[str, LayoutDef] = {ld.layout_id: ld for ld in LAYOUT_CATALOG}

# IDs that the config property may store:
VALID_LAYOUT_IDS: frozenset[str] = frozenset(_LAYOUT_BY_ID)


def get_layout_def(layout_id: str) -> LayoutDef:
    """Return the :class:`LayoutDef` for *layout_id*, or ``"auto"`` if unknown."""
    return _LAYOUT_BY_ID.get(str(layout_id).strip().lower(), _LAYOUT_BY_ID["auto"])
