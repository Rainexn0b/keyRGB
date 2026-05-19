from __future__ import annotations

from types import SimpleNamespace

from src.core.effects.catalog import REACTIVE_EFFECTS
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.utils.safe_attrs import safe_bool_attr, safe_int_attr, safe_str_attr
from src.tray.pollers.config_polling_internal._config_apply_state import _safe_perkey_signature, _safe_tuple_attr
from src.tray.pollers.config_polling_internal._config_apply_state import ConfigApplyState, build_config_apply_state


def test_build_config_apply_state_reads_config_without_tray_protocol() -> None:
    reactive_effect = REACTIVE_EFFECTS[0]
    config = SimpleNamespace(
        effect=reactive_effect,
        speed=5,
        brightness=35,
        color=(5, 6, 7),
        per_key_colors={1: (1, 2, 3)},
        reactive_use_manual_color=True,
        reactive_color=(10, 20, 30),
        reactive_brightness=22,
        reactive_trail_percent=73,
        software_effect_target="keyboard",
    )
    resolved_effects: list[str] = []

    def _resolve_effect_name(effect_name: str) -> str:
        resolved_effects.append(effect_name)
        return effect_name

    state = build_config_apply_state(
        config,
        resolve_effect_name=_resolve_effect_name,
        read_bool_attr=safe_bool_attr,
        read_int_attr=safe_int_attr,
        read_str_attr=safe_str_attr,
        read_tuple_attr=_safe_tuple_attr,
        read_perkey_signature=_safe_perkey_signature,
        normalize_software_effect_target_fn=normalize_software_effect_target,
        reactive_effects_set=frozenset(REACTIVE_EFFECTS),
    )

    assert resolved_effects == [reactive_effect]
    assert state == ConfigApplyState(
        effect=reactive_effect,
        speed=5,
        brightness=35,
        color=(5, 6, 7),
        perkey_sig=((1, (1, 2, 3)),),
        reactive_use_manual=True,
        reactive_color=(10, 20, 30),
        reactive_brightness=22,
        reactive_trail_percent=73,
        software_effect_target="keyboard",
    )


def test_build_config_apply_state_promotes_base_only_state_to_runtime_perkey() -> None:
    class _BaseOnlyPerkeyConfig:
        effect = "none"
        speed = 2
        color = (4, 5, 6)
        per_key_colors = {(0, 0): (1, 2, 3)}
        reactive_use_manual_color = False
        reactive_color = (10, 20, 30)
        software_effect_target = "keyboard"
        perkey_brightness = 35

        @property
        def brightness(self) -> int:
            return self.perkey_brightness

    config = _BaseOnlyPerkeyConfig()

    state = build_config_apply_state(
        config,
        resolve_effect_name=lambda effect_name: effect_name,
        read_bool_attr=safe_bool_attr,
        read_int_attr=safe_int_attr,
        read_str_attr=safe_str_attr,
        read_tuple_attr=_safe_tuple_attr,
        read_perkey_signature=_safe_perkey_signature,
        normalize_software_effect_target_fn=normalize_software_effect_target,
        reactive_effects_set=frozenset(REACTIVE_EFFECTS),
    )

    assert state.effect == "perkey"
    assert state.selected_effect == "none"
    assert state.brightness == 35
    assert state.perkey_sig == (((0, 0), (1, 2, 3)),)
