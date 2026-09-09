"""Settings category navigation (UX-01).

Owns the stable category model for the tabbed Settings window and builds one
independently scrolling page per category. Panel construction stays in
``window.py``; this module only owns category metadata and page shells so tab
switches never recreate panels or repeat probes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tkinter import ttk

    from .scrollable_area import ScrollableArea


@dataclass(frozen=True)
class SettingsCategory:
    """One Settings notebook tab."""

    id: str
    title: str
    panels: tuple[str, ...]


CATEGORIES: tuple[SettingsCategory, ...] = (
    SettingsCategory(id="lighting_power", title="Lighting & Power", panels=("management", "power_source")),
    SettingsCategory(id="automation", title="Automation", panels=("dim_sync", "time_scheduler")),
    SettingsCategory(id="app", title="App", panels=("autostart",)),
    SettingsCategory(id="advanced", title="Advanced", panels=("idle_transition_advanced", "experimental")),
    SettingsCategory(id="about", title="About & Support", panels=("version",)),
)

DEFAULT_CATEGORY_ID = "lighting_power"

CATEGORY_IDS: tuple[str, ...] = tuple(category.id for category in CATEGORIES)
CATEGORY_TITLES: tuple[str, ...] = tuple(category.title for category in CATEGORIES)
CATEGORY_BY_ID: dict[str, SettingsCategory] = {category.id: category for category in CATEGORIES}


@dataclass
class SettingsNavigation:
    """Built notebook plus per-category page shells."""

    notebook: ttk.Notebook
    page_frames: dict[str, ttk.Frame] = field(default_factory=dict)
    scroll_areas: dict[str, ScrollableArea] = field(default_factory=dict)
    panel_parents: dict[str, ttk.Frame] = field(default_factory=dict)


def build_navigation(
    parent: object,
    *,
    notebook_cls: Callable[..., ttk.Notebook],
    frame_cls: Callable[..., ttk.Frame],
    scroll_area_cls: Callable[..., ScrollableArea],
    bg_color: str,
    padding: int = 10,
) -> SettingsNavigation:
    """Create the notebook and one scroll area per category.

    Classes are injected so ``window.py`` keeps its existing ``ttk`` /
    ``ScrollableArea`` monkeypatch seams and unit tests can pass fakes.
    Every page is constructed exactly once here; tab switches only reselect.
    ``panel_parents`` maps each panel id declared in ``CATEGORIES`` to its
    category page's scroll content frame, so panel placement cannot drift
    from the category model.
    """
    notebook = notebook_cls(parent)
    page_frames: dict[str, ttk.Frame] = {}
    scroll_areas: dict[str, ScrollableArea] = {}
    panel_parents: dict[str, ttk.Frame] = {}
    for category in CATEGORIES:
        page = frame_cls(notebook)
        notebook.add(page, text=category.title)
        scroll = scroll_area_cls(page, bg_color=bg_color, padding=padding)
        page_frames[category.id] = page
        scroll_areas[category.id] = scroll
        for panel_id in category.panels:
            panel_parents[panel_id] = scroll.frame
    notebook.select(page_frames[DEFAULT_CATEGORY_ID])
    return SettingsNavigation(
        notebook=notebook,
        page_frames=page_frames,
        scroll_areas=scroll_areas,
        panel_parents=panel_parents,
    )
