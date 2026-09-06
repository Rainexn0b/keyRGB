from __future__ import annotations

from collections.abc import Callable

from keyrgb.tray.protocols import LightingTrayProtocol


def prepare_effect_engine_state(
    tray: LightingTrayProtocol,
    *,
    effect: str,
    is_software_effect_fn: Callable[[str], bool],
    set_engine_perkey_from_config_fn: Callable[[LightingTrayProtocol], None],
    clear_engine_perkey_state_fn: Callable[[LightingTrayProtocol], None],
) -> None:
    """Prepare engine per-key state before starting an effect."""

    if is_software_effect_fn(effect):
        set_engine_perkey_from_config_fn(tray)
    else:
        clear_engine_perkey_state_fn(tray)
