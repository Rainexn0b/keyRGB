"""App/session and physical-layout config accessors."""

from __future__ import annotations

from typing import Any

from src.core.effects import software_targets as _software_targets

from ._lighting import _props as _config_props


class AppConfigAccessors:
    """Autostart, experimental flags, and layout target accessors for ``Config``."""

    _settings: dict[str, Any]

    def _save(self) -> None: ...

    autostart = _config_props.bool_prop("autostart", default=True)
    experimental_backends_enabled = _config_props.bool_prop("experimental_backends_enabled", default=False)
    os_autostart = _config_props.bool_prop("os_autostart", default=False)

    # Physical keyboard layout for the per-key editor / calibrator overlay.
    physical_layout = _config_props.enum_prop(
        "physical_layout",
        default="auto",
        allowed=("auto", "ansi", "iso", "ks", "abnt", "jis"),
    )

    software_effect_target = _config_props.enum_prop(
        "software_effect_target",
        default="keyboard",
        allowed=_software_targets.SOFTWARE_EFFECT_TARGETS,
    )
