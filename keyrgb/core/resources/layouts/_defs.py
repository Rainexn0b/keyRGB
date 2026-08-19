"""LayoutDef — metadata record for one physical keyboard layout variant."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutDef:
    """Describes one physical keyboard layout variant.

    Attributes
    ----------
    layout_id:
        Machine-readable identifier stored in config (e.g. ``"ansi"``).
        ``"auto"`` is a special sentinel: it triggers sysfs-based detection
        at runtime and is resolved to a concrete layout before rendering.
    label:
        Human-readable display name shown in UI dropdowns.
    """

    layout_id: str
    label: str
