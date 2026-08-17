from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.core.profile.runtime_activation import activate_perkey_profile_runtime


def test_activate_perkey_profile_runtime_uses_in_place_transition_without_power_marker() -> None:
    config = SimpleNamespace()
    apply_transition = MagicMock(return_value=True)
    start_effect = MagicMock()
    update_icon = MagicMock()
    update_menu = MagicMock()
    set_is_off = MagicMock()
    set_active_profile = MagicMock(return_value="battery")
    load_per_key_colors = MagicMock(return_value={(0, 0): (1, 2, 3)})
    apply_profile_to_config = MagicMock()

    result = activate_perkey_profile_runtime(
        config,
        "battery",
        set_active_profile_fn=set_active_profile,
        load_per_key_colors_fn=load_per_key_colors,
        apply_profile_to_config_fn=apply_profile_to_config,
        is_power_forced_off_fn=lambda: False,
        set_is_off_fn=set_is_off,
        apply_runtime_transition_fn=apply_transition,
        start_current_effect_fn=start_effect,
        update_icon_fn=update_icon,
        update_menu_fn=update_menu,
    )

    assert result.name == "battery"
    assert result.runtime_applied is True
    assert result.used_in_place_transition is True
    set_active_profile.assert_called_once_with("battery")
    load_per_key_colors.assert_called_once_with("battery")
    apply_profile_to_config.assert_called_once_with(config, {(0, 0): (1, 2, 3)})
    apply_transition.assert_called_once_with()
    start_effect.assert_not_called()
    update_icon.assert_called_once_with()
    update_menu.assert_called_once_with()
    set_is_off.assert_called_once_with(False)


def test_activate_perkey_profile_runtime_marks_power_source_transition_and_restarts_on_decline() -> None:
    config = SimpleNamespace()
    apply_transition = MagicMock(return_value=False)
    start_effect = MagicMock()
    mark_transition = MagicMock()

    result = activate_perkey_profile_runtime(
        config,
        "battery",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (9, 9, 9)},
        apply_profile_to_config_fn=lambda cfg, colors: setattr(cfg, "per_key_colors", colors),
        is_power_forced_off_fn=lambda: False,
        set_is_off_fn=lambda value: setattr(config, "is_off", value),
        apply_runtime_transition_fn=apply_transition,
        start_current_effect_fn=start_effect,
        update_icon_fn=lambda: None,
        update_menu_fn=lambda: None,
        mark_power_source_transition_fn=mark_transition,
        mark_power_source_transition=True,
        monotonic_fn=lambda: 123.0,
    )

    apply_transition.assert_called_once_with()
    start_effect.assert_called_once_with()
    mark_transition.assert_called_once_with("battery", 123.0)
    assert result.used_in_place_transition is False
    assert config.per_key_colors == {(0, 0): (9, 9, 9)}


def test_activate_perkey_profile_runtime_can_skip_menu_refresh() -> None:
    update_icon = MagicMock()
    update_menu = MagicMock()

    activate_perkey_profile_runtime(
        SimpleNamespace(),
        "battery",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (9, 9, 9)},
        apply_profile_to_config_fn=lambda _config, _colors: None,
        is_power_forced_off_fn=lambda: False,
        apply_runtime_transition_fn=lambda: True,
        update_icon_fn=update_icon,
        update_menu_fn=update_menu,
        refresh_menu=False,
    )

    update_icon.assert_called_once_with()
    update_menu.assert_not_called()


def test_activate_perkey_profile_runtime_passes_secondary_payload_when_present() -> None:
    config = SimpleNamespace()
    apply_profile_to_config = MagicMock()
    store_secondary = MagicMock()
    secondary = {"version": 1, "areas": {"logo": {"enabled": True, "color": [1, 2, 3]}}}

    result = activate_perkey_profile_runtime(
        config,
        "profile-with-areas",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (9, 9, 9)},
        apply_profile_to_config_fn=apply_profile_to_config,
        load_secondary_lighting_fn=lambda _name: secondary,
        store_secondary_lighting_fn=store_secondary,
        is_power_forced_off_fn=lambda: False,
        apply_runtime_transition_fn=lambda: True,
        update_icon_fn=lambda: None,
    )

    apply_profile_to_config.assert_called_once_with(
        config,
        {(0, 0): (9, 9, 9)},
        secondary_lighting=secondary,
    )
    store_secondary.assert_called_once_with(secondary)
    assert result.secondary_lighting is secondary


def test_activate_legacy_profile_does_not_clear_missing_secondary_payload() -> None:
    store_secondary = MagicMock()

    result = activate_perkey_profile_runtime(
        SimpleNamespace(),
        "legacy-profile",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (9, 9, 9)},
        apply_profile_to_config_fn=MagicMock(),
        load_secondary_lighting_fn=lambda _name: None,
        store_secondary_lighting_fn=store_secondary,
        is_power_forced_off_fn=lambda: False,
        apply_runtime_transition_fn=lambda: True,
        update_icon_fn=lambda: None,
    )

    store_secondary.assert_not_called()
    assert result.secondary_lighting is None


def test_activate_perkey_profile_runtime_skips_runtime_apply_while_power_forced_off() -> None:
    apply_transition = MagicMock(return_value=True)
    start_effect = MagicMock()
    set_is_off = MagicMock()
    mark_transition = MagicMock()
    apply_profile_to_config = MagicMock()

    result = activate_perkey_profile_runtime(
        SimpleNamespace(),
        "default",
        set_active_profile_fn=lambda name: name,
        load_per_key_colors_fn=lambda _name: {(0, 0): (1, 2, 3)},
        apply_profile_to_config_fn=apply_profile_to_config,
        is_power_forced_off_fn=lambda: True,
        set_is_off_fn=set_is_off,
        apply_runtime_transition_fn=apply_transition,
        start_current_effect_fn=start_effect,
        update_icon_fn=lambda: None,
        update_menu_fn=lambda: None,
        mark_power_source_transition_fn=mark_transition,
        mark_power_source_transition=True,
        monotonic_fn=lambda: 42.0,
    )

    apply_profile_to_config.assert_called_once()
    apply_transition.assert_not_called()
    start_effect.assert_not_called()
    set_is_off.assert_not_called()
    mark_transition.assert_called_once_with("default", 42.0)
    assert result.runtime_applied is False


def test_activation_applies_config_before_effect_and_ui_callbacks() -> None:
    events: list[str] = []

    activate_perkey_profile_runtime(
        SimpleNamespace(),
        "ordered",
        set_active_profile_fn=lambda name: events.append("activate") or name,
        load_per_key_colors_fn=lambda _name: events.append("load") or {(0, 0): (1, 2, 3)},
        apply_profile_to_config_fn=lambda _config, _colors: events.append("config"),
        is_power_forced_off_fn=lambda: False,
        set_is_off_fn=lambda _value: events.append("is_off"),
        apply_runtime_transition_fn=lambda: events.append("transition") or False,
        start_current_effect_fn=lambda: events.append("effect"),
        update_icon_fn=lambda: events.append("icon"),
        update_menu_fn=lambda: events.append("menu"),
    )

    assert events == ["activate", "load", "config", "is_off", "transition", "effect", "icon", "menu"]


def test_core_activation_has_no_private_tray_method_contract() -> None:
    from pathlib import Path

    source = Path("src/core/profile/runtime_activation.py").read_text(encoding="utf-8")

    assert "getattr(tray" not in source
    assert "vars(tray)" not in source
    assert "setattr(tray" not in source
    assert "_start_current_effect" not in source
    assert "_update_icon" not in source
    assert "_update_menu" not in source
    assert "_apply_power_source_perkey_profile_transition" not in source
    assert "_last_power_source_transition_at" not in source
    assert "_active_secondary_lighting" not in source
    assert "_resolve_tray_callback" not in source
