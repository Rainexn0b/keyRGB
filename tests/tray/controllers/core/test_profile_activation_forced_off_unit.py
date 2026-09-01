"""Regression tests for the power-source/idle-off race in profile activation.

These exercise the two production wiring paths that feed core
``activate_perkey_profile_runtime`` with the unified forced-off facade:

- ``keyrgb.tray.controllers.profile_activation.activate_perkey_profile_on_tray``
  (tray menu / external activation)
- ``keyrgb.core.power.management.manager.activate_perkey_profile``
  (power-source per-key profile activation)

Both must persist profile/config intent and the power-source transition marker
even while ANY forced-off owner (user, power/suspend/lid, or idle/screen-off)
holds the deck dark, but must NOT reset ``is_off``, apply an in-place transition,
or start an effect during that suppression.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.tray.fakes import make_owner_backed_simple_tray


def _patch_core_profiles_for_tray():
    """Patch the profile fakes used by the tray wiring import path.

    Returns ``(patcher, mocks)`` where ``mocks`` is the caller's own reference to
    the mock objects so assertions are unaffected by ``patch.multiple``'s yielded
    dict (which only contains auto-created mocks).
    """

    mocks = {
        "set_active_profile": MagicMock(return_value="battery"),
        "load_per_key_colors": MagicMock(return_value={(0, 0): (1, 2, 3)}),
        "apply_profile_to_config": MagicMock(),
        "load_secondary_lighting": MagicMock(return_value=None),
    }
    patcher = patch.multiple(
        "keyrgb.tray.controllers.profile_activation.core_profiles",
        **mocks,
    )
    return patcher, mocks


def _patch_core_profiles_for_manager():
    """Patch the profile fakes used by the power-manager wiring import path."""

    mocks = {
        "set_active_profile": MagicMock(return_value="battery"),
        "load_per_key_colors": MagicMock(return_value={(0, 0): (1, 2, 3)}),
        "apply_profile_to_config": MagicMock(),
        "load_secondary_lighting": MagicMock(return_value=None),
    }
    patcher = patch.multiple(
        "keyrgb.core.power.management.manager.perkey_profiles",
        **mocks,
    )
    return patcher, mocks


# ---- tray wiring: suppression while idle/user forced off -----------------


def test_tray_activation_suppresses_runtime_while_user_forced_off() -> None:
    from keyrgb.tray.controllers.profile_activation import activate_perkey_profile_on_tray

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        user_forced_off=True,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
        _update_menu=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_tray()
    with patcher:
        result = activate_perkey_profile_on_tray(
            tray, "battery", mark_power_source_transition=True, monotonic_fn=lambda: 99.0
        )

    # Persisted intent + transition marker still update.
    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at == 99.0
    assert tray._last_power_source_transition_profile_name == "battery"
    # Runtime application suppressed: deck stays dark, no transition/effect.
    assert tray.is_off is True
    tray._apply_power_source_perkey_profile_transition.assert_not_called()
    tray._start_current_effect.assert_not_called()
    assert result.runtime_applied is False
    # UI refresh still happens (icon/menu), only hardware/effect suppressed.
    tray._update_icon.assert_called_once_with()


def test_tray_activation_suppresses_runtime_while_idle_forced_off() -> None:
    from keyrgb.tray.controllers.profile_activation import activate_perkey_profile_on_tray

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        idle_forced_off=True,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
        _update_menu=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_tray()
    with patcher:
        result = activate_perkey_profile_on_tray(
            tray, "battery", mark_power_source_transition=True, monotonic_fn=lambda: 101.0
        )

    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at == 101.0
    assert tray._last_power_source_transition_profile_name == "battery"
    assert tray.is_off is True
    tray._apply_power_source_perkey_profile_transition.assert_not_called()
    tray._start_current_effect.assert_not_called()
    assert result.runtime_applied is False


def test_tray_activation_applies_runtime_when_not_forced_off() -> None:
    from keyrgb.tray.controllers.profile_activation import activate_perkey_profile_on_tray

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
        _update_menu=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_tray()
    with patcher:
        result = activate_perkey_profile_on_tray(
            tray, "battery", mark_power_source_transition=True, monotonic_fn=lambda: 50.0
        )

    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at == 50.0
    # Ordinary activation still clears is_off and applies the transition.
    assert tray.is_off is False
    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    tray._start_current_effect.assert_not_called()
    assert result.runtime_applied is True


# ---- power-source wiring: suppression while idle/user forced off ---------


def test_power_source_activation_suppresses_runtime_while_user_forced_off() -> None:
    from keyrgb.core.power.management.manager import activate_perkey_profile

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        user_forced_off=True,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_manager()
    with patcher:
        activate_perkey_profile(tray, "battery")

    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at is not None
    assert tray._last_power_source_transition_profile_name == "battery"
    assert tray.tray_idle_power_state.last_power_source_transition_at is not None
    # Runtime application suppressed: deck stays dark, no transition/effect.
    assert tray.is_off is True
    tray._apply_power_source_perkey_profile_transition.assert_not_called()
    tray._start_current_effect.assert_not_called()


def test_power_source_activation_suppresses_runtime_while_idle_forced_off() -> None:
    from keyrgb.core.power.management.manager import activate_perkey_profile

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        idle_forced_off=True,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_manager()
    with patcher:
        activate_perkey_profile(tray, "battery")

    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at is not None
    assert tray._last_power_source_transition_profile_name == "battery"
    assert tray.is_off is True
    tray._apply_power_source_perkey_profile_transition.assert_not_called()
    tray._start_current_effect.assert_not_called()


def test_power_source_activation_applies_runtime_when_not_forced_off() -> None:
    from keyrgb.core.power.management.manager import activate_perkey_profile

    tray = make_owner_backed_simple_tray(
        config=SimpleNamespace(),
        is_off=True,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
        _apply_power_source_perkey_profile_transition=MagicMock(return_value=True),
        _start_current_effect=MagicMock(),
        _update_icon=MagicMock(),
    )

    patcher, profiles = _patch_core_profiles_for_manager()
    with patcher:
        activate_perkey_profile(tray, "battery")

    profiles["apply_profile_to_config"].assert_called_once()
    assert tray._last_power_source_transition_at is not None
    assert tray._last_power_source_transition_profile_name == "battery"
    # Ordinary activation clears is_off and applies the transition.
    assert tray.is_off is False
    tray._apply_power_source_perkey_profile_transition.assert_called_once_with()
    tray._start_current_effect.assert_not_called()
