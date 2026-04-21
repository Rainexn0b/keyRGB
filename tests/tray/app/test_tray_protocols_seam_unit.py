"""Seam tests for tray protocol state management.

These tests verify the Round 1 refactoring of tray icon state ownership
and the ensure_tray_icon_state fallback behavior.
"""

from types import SimpleNamespace

from src.tray.protocols import TrayIconState, ensure_tray_icon_state


def test_ensure_tray_icon_state_returns_owned_instance():
    """When tray has a valid tray_icon_state, return that SAME object (identity check)."""
    # Arrange: Create a tray object with a pre-owned TrayIconState
    owned_state = TrayIconState(visual=None, animating=False)
    tray = SimpleNamespace(tray_icon_state=owned_state)

    # Act: Call ensure_tray_icon_state
    result = ensure_tray_icon_state(tray)

    # Assert: Result is the SAME object (identity, not just equality)
    assert result is owned_state


def test_ensure_tray_icon_state_returns_fresh_on_missing_attr():
    """When tray lacks tray_icon_state, return fresh instance WITHOUT mutating the tray."""
    # Arrange: Create a tray object without tray_icon_state
    tray = SimpleNamespace()

    # Act: Call ensure_tray_icon_state
    result = ensure_tray_icon_state(tray)

    # Assert: Result is a fresh TrayIconState instance
    assert isinstance(result, TrayIconState)

    # Assert: No side-effect mutation—tray_icon_state was NOT added to tray
    assert not hasattr(tray, "tray_icon_state")


def test_ensure_tray_icon_state_returns_fresh_on_wrong_type():
    """When tray.tray_icon_state is wrong type, return fresh instance without using it."""
    # Arrange: Create a tray with tray_icon_state set to a non-TrayIconState value
    wrong_value = object()
    tray = SimpleNamespace(tray_icon_state=wrong_value)

    # Act: Call ensure_tray_icon_state
    result = ensure_tray_icon_state(tray)

    # Assert: Result is a fresh TrayIconState (not the wrong-type value)
    assert isinstance(result, TrayIconState)
    assert result is not wrong_value
