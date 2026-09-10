"""Guided config view: layout overrides without persisting guided state."""

from __future__ import annotations

from pathlib import Path


def guided_session_path_of(app: object) -> Path | None:
    """Return the guided session path for an app-like, or ``None`` standalone.

    Narrow legacy compatibility shim: unbound-method unit doubles predate
    guided mode and carry no ``guided_session_path`` attribute; absence means
    standalone profile behavior.  This is the only untyped attribute read in
    the guided app surface.
    """

    raw = getattr(app, "guided_session_path", None)
    if raw is None:
        return None
    if isinstance(raw, Path):
        return raw
    return Path(str(raw)).expanduser()


class GuidedConfigView:
    """Read-through view over ``Config`` with guided layout overrides.

    ``physical_layout`` and ``layout_legend_pack`` return the session draft
    values so every downstream layout/legend resolution (visible keys,
    hit-testing, canvas redraw, probe canonicalization) follows the guided
    draft.  All other attribute reads and every write forward to the wrapped
    ``Config`` so Config-mediated preview mutations still reach the real
    configuration, and nothing guided is ever persisted: the overrides live
    only on this view object, never in ``Config._settings``.
    """

    def __init__(self, base_config: object, *, physical_layout: str, legend_pack: str | None) -> None:
        object.__setattr__(self, "_base_config", base_config)
        object.__setattr__(self, "_guided_physical_layout", physical_layout)
        object.__setattr__(self, "_guided_legend_pack", legend_pack)

    @property
    def physical_layout(self) -> str:
        override = self.__dict__.get("_guided_physical_layout")
        if isinstance(override, str) and override.strip():
            return override
        return object.__getattribute__(self, "_base_config").physical_layout

    @property
    def layout_legend_pack(self) -> str:
        override = self.__dict__.get("_guided_legend_pack")
        if isinstance(override, str) and override.strip():
            return override
        return object.__getattribute__(self, "_base_config").layout_legend_pack

    @property
    def CONFIG_DIR(self) -> Path:
        return object.__getattribute__(self, "_base_config").CONFIG_DIR

    @property
    def CONFIG_FILE(self) -> Path:
        return object.__getattribute__(self, "_base_config").CONFIG_FILE

    def __getattr__(self, name: str) -> object:
        return getattr(object.__getattribute__(self, "_base_config"), name)

    def __setattr__(self, name: str, value: object) -> None:
        setattr(object.__getattribute__(self, "_base_config"), name, value)
