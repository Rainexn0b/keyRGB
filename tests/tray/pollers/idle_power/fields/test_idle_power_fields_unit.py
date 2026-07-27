"""Direct unit coverage for tray idle/power field bridge helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray import _idle_power_fields as fields

# Import public package first to avoid circular import with _idle_power_fields.
from src.tray.idle_power_state import ensure_tray_idle_power_state


def test_normalize_field_names_and_aliases() -> None:
    attr, state = fields._normalize_idle_power_field_names(
        attr_name="idle_forced_off",
        state_name="idle_forced_off",
        alias_kwargs={},
    )
    assert attr == "idle_forced_off"
    assert state == "idle_forced_off"

    attr, state = fields._normalize_idle_power_field_names(
        attr_name=None,
        state_name=None,
        alias_kwargs={"legacy_attr": "a", "owner_attr": "b"},
    )
    assert (attr, state) == ("a", "b")

    with pytest.raises(TypeError, match="multiple values for attr_name"):
        fields._normalize_idle_power_field_names(
            attr_name="x",
            state_name="y",
            alias_kwargs={"legacy_attr": "z"},
        )
    with pytest.raises(TypeError, match="multiple values for state_name"):
        fields._normalize_idle_power_field_names(
            attr_name="x",
            state_name="y",
            alias_kwargs={"owner_attr": "z"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        fields._normalize_idle_power_field_names(
            attr_name="x",
            state_name="y",
            alias_kwargs={"nope": 1},
        )
    with pytest.raises(TypeError, match="missing required keyword argument: attr_name"):
        fields._normalize_idle_power_field_names(attr_name=None, state_name="y", alias_kwargs={})
    with pytest.raises(TypeError, match="missing required keyword argument: state_name"):
        fields._normalize_idle_power_field_names(attr_name="x", state_name=None, alias_kwargs={})


def test_coerce_helpers() -> None:
    assert fields._coerce_idle_power_bool(True) == (True, True)
    assert fields._coerce_idle_power_bool(0) == (False, True)
    assert fields._coerce_idle_power_bool("yes") == (True, True)
    assert fields._coerce_idle_power_bool(b"off") == (False, True)
    assert fields._coerce_idle_power_bool("maybe") == (False, False)
    assert fields._coerce_idle_power_bool(object()) == (False, False)

    assert fields._coerce_idle_power_optional_int(None) == (None, True)
    assert fields._coerce_idle_power_optional_int(True) == (None, False)
    assert fields._coerce_idle_power_optional_int("12") == (12, True)
    assert fields._coerce_idle_power_optional_int("x") == (None, False)
    assert fields._coerce_idle_power_optional_int(object()) == (None, False)

    assert fields._coerce_idle_power_optional_bool(None) == (None, True)
    assert fields._coerce_idle_power_optional_bool("on") == (True, True)
    assert fields._coerce_idle_power_optional_bool("maybe") == (None, False)

    assert fields._coerce_idle_power_float(True) == (0.0, False)
    assert fields._coerce_idle_power_float("1.5") == (1.5, True)
    assert fields._coerce_idle_power_float("bad") == (0.0, False)
    assert fields._coerce_idle_power_float(object()) == (0.0, False)


def test_sync_set_clear_and_read_fields() -> None:
    tray = SimpleNamespace(idle_forced_off=True)
    assert fields.sync_idle_power_state_field(tray, attr_name="idle_forced_off", state_name="idle_forced_off") is True
    state = ensure_tray_idle_power_state(tray)
    assert state.idle_forced_off is True

    # owner seeds tray when attr not in instance dict
    tray2 = SimpleNamespace()
    ensure_tray_idle_power_state(tray2).last_brightness = 40
    assert fields.sync_idle_power_state_field(tray2, attr_name="last_brightness", state_name="last_brightness") == 40
    assert tray2.last_brightness == 40

    tray3 = SimpleNamespace()
    fields.set_idle_power_state_field(tray3, attr_name="dim_temp_active", state_name="dim_temp_active", value=True)
    assert tray3.dim_temp_active is True
    assert ensure_tray_idle_power_state(tray3).dim_temp_active is True

    # property-backed tray skips dual-write
    class _PropTray:
        @property
        def idle_forced_off(self) -> bool:
            return bool(ensure_tray_idle_power_state(self).idle_forced_off)

    prop_tray = _PropTray()
    fields.set_idle_power_state_field(prop_tray, attr_name="idle_forced_off", state_name="idle_forced_off", value=True)
    assert ensure_tray_idle_power_state(prop_tray).idle_forced_off is True

    tray4 = SimpleNamespace(user_forced_off=True)
    fields.clear_idle_power_state_field(
        tray4,
        attr_name="user_forced_off",
        state_name="user_forced_off",
        value=False,
    )
    assert "user_forced_off" not in vars(tray4)
    assert ensure_tray_idle_power_state(tray4).user_forced_off is False


def test_read_converged_bool_int_float_fields() -> None:
    tray = SimpleNamespace(idle_forced_off="yes")
    assert (
        fields.read_idle_power_state_bool_field(tray, attr_name="idle_forced_off", state_name="idle_forced_off") is True
    )

    tray_i = SimpleNamespace(last_brightness="33")
    assert (
        fields.read_idle_power_state_optional_int_field(
            tray_i,
            attr_name="last_brightness",
            state_name="last_brightness",
        )
        == 33
    )

    # Invalid instance attr falls back to the typed owner default (25).
    tray_bad = SimpleNamespace(last_brightness=object())
    assert (
        fields.read_idle_power_state_optional_int_field(
            tray_bad,
            attr_name="last_brightness",
            state_name="last_brightness",
            default=7,
        )
        == 25
    )

    # When owner is also invalid, explicit default wins.
    tray_both = SimpleNamespace(last_brightness=object())
    ensure_tray_idle_power_state(tray_both).last_brightness = object()  # type: ignore[assignment]
    assert (
        fields.read_idle_power_state_optional_int_field(
            tray_both,
            attr_name="last_brightness",
            state_name="last_brightness",
            default=7,
        )
        == 7
    )

    tray_ob = SimpleNamespace(dim_temp_active="off")
    assert (
        fields.read_idle_power_state_optional_bool_field(
            tray_ob,
            attr_name="dim_temp_active",
            state_name="dim_temp_active",
        )
        is False
    )

    tray_f = SimpleNamespace(last_idle_turn_off_at="2.5")
    assert (
        fields.read_idle_power_state_float_field(
            tray_f,
            attr_name="last_idle_turn_off_at",
            state_name="last_idle_turn_off_at",
        )
        == 2.5
    )

    # Invalid instance attr falls back to typed owner default (0.0).
    tray_fb = SimpleNamespace(last_idle_turn_off_at=object())
    assert (
        fields.read_idle_power_state_float_field(
            tray_fb,
            attr_name="last_idle_turn_off_at",
            state_name="last_idle_turn_off_at",
            default=1.25,
        )
        == 0.0
    )
