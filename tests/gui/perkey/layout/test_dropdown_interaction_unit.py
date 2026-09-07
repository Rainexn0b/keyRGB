from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.gui.perkey.layout._dropdown_fakes import (
    _FakeAnchor,
    _FakeListbox,
    _FakePopup,
    _install_fake_tk,
    _make_dropdown,
)


def test_motion_handler_updates_hover_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_tk(monkeypatch)
    widget, _chosen = _make_dropdown(current="")

    widget.open()

    listbox = registry["listbox"]
    assert isinstance(listbox, _FakeListbox)
    listbox.nearest_result = 2

    motion_handler = listbox.bound_callbacks["<Motion>"]
    motion_handler(SimpleNamespace(y=999))

    assert listbox.selection_clear_calls == [(0, "end")]
    assert listbox.selection == [2]
    assert listbox.activate_calls == [2]


def test_commit_uses_selected_value_and_closes_popup(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_tk(monkeypatch)
    widget, chosen = _make_dropdown(current="third")

    widget.open()

    popup = registry["popup"]
    listbox = registry["listbox"]
    assert isinstance(popup, _FakePopup)
    assert isinstance(listbox, _FakeListbox)

    commit_handler = listbox.bound_callbacks["<ButtonRelease-1>"]
    commit_handler(SimpleNamespace())

    assert chosen == ["third"]
    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1


@pytest.mark.parametrize("mode", ["missing_selection", "get_error"])
def test_commit_closes_when_selection_is_missing_or_listbox_errors(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    registry = _install_fake_tk(monkeypatch)
    widget, chosen = _make_dropdown(current="")

    widget.open()

    popup = registry["popup"]
    listbox = registry["listbox"]
    assert isinstance(popup, _FakePopup)
    assert isinstance(listbox, _FakeListbox)

    if mode == "missing_selection":
        listbox.selection = []
    else:
        listbox.selection = [1]
        listbox.failures["get"] = RuntimeError("broken listbox")

    commit_handler = listbox.bound_callbacks["<Return>"]
    commit_handler(SimpleNamespace())

    assert chosen == []
    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1


def test_open_places_popup_below_anchor_when_above_would_go_off_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor = _FakeAnchor(x=14, y=15, width=120, height=18)
    registry = _install_fake_tk(monkeypatch, popup_reqheight=40)
    widget, _chosen = _make_dropdown(anchor=anchor)

    widget.open()

    popup = registry["popup"]
    assert isinstance(popup, _FakePopup)
    assert popup.geometry_calls == ["120x40+14+33"]


def test_click_outside_handler_closes_when_event_has_no_widget(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_tk(monkeypatch)
    widget, _chosen = _make_dropdown()

    widget.open()

    popup = registry["popup"]
    assert isinstance(popup, _FakePopup)

    click_handler = popup.bound_callbacks["<Button-1>"]
    click_handler(SimpleNamespace())

    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1
