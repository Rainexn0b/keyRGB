from __future__ import annotations

import pytest

from tests.gui.perkey.layout._dropdown_fakes import (
    _FakeAnchor,
    _FakeListbox,
    _FakePopup,
    _FakeRoot,
    _install_fake_tk,
    _make_dropdown,
)


def test_close_is_idempotent_and_updates_open_state() -> None:
    widget, _chosen = _make_dropdown()
    popup = _FakePopup(object())
    widget._win = popup

    assert widget.is_open() is True

    widget.close()

    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1

    widget.close()

    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1


def test_close_tolerates_runtime_teardown_failures() -> None:
    widget, _chosen = _make_dropdown()
    popup = _FakePopup(
        object(),
        failures={
            "grab_release": RuntimeError("grab release failed"),
            "destroy": RuntimeError("destroy failed"),
        },
    )
    widget._win = popup

    widget.close()

    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1


def test_open_returns_break_without_creating_popup_when_values_provider_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_tk(monkeypatch)
    widget, _chosen = _make_dropdown(values=())

    assert widget.open() == "break"
    assert widget.is_open() is False
    assert registry["popup_count"] == 0
    assert registry["listbox_count"] == 0


def test_open_returns_break_and_closes_existing_popup_when_already_open() -> None:
    widget, _chosen = _make_dropdown()
    popup = _FakePopup(object())
    widget._win = popup

    assert widget.open() == "break"
    assert widget.is_open() is False
    assert popup.grab_release_calls == 1
    assert popup.destroy_calls == 1


@pytest.mark.parametrize(
    ("prefers_dark", "expected_selectbackground"),
    [
        (True, "#4a4a4a"),
        (False, "#3399ff"),
        (None, "#4a4a4a"),
    ],
)
def test_open_builds_popup_with_current_selection_and_theme_sensitive_highlight(
    monkeypatch: pytest.MonkeyPatch,
    prefers_dark: bool | None,
    expected_selectbackground: str,
) -> None:
    root = _FakeRoot()
    anchor = _FakeAnchor(x=25, y=120, width=90, height=18)
    registry = _install_fake_tk(monkeypatch, prefers_dark=prefers_dark)
    widget, _chosen = _make_dropdown(root=root, anchor=anchor, current=" second ")

    assert widget.open() == "break"

    popup = registry["popup"]
    listbox = registry["listbox"]

    assert isinstance(popup, _FakePopup)
    assert isinstance(listbox, _FakeListbox)
    assert widget.is_open() is True
    assert popup.parent is root
    assert popup.withdraw_calls == 1
    assert popup.transient_calls == [root]
    assert popup.overrideredirect_calls == [True]
    assert popup.attributes_calls == [("-type", "combo")]
    assert popup.configure_calls == [{"bg": "#101010"}]
    assert popup.geometry_calls == ["90x40+25+80"]
    assert popup.deiconify_calls == 1
    assert popup.lift_calls == 1
    assert popup.grab_set_calls == 1
    assert popup.focus_force_calls == 1
    assert root.bind_calls == [("<Destroy>", widget.close, True)]

    assert listbox.parent is popup
    assert listbox.options["bg"] == "#101010"
    assert listbox.options["fg"] == "#efefef"
    assert listbox.options["height"] == 3
    assert listbox.options["selectbackground"] == expected_selectbackground
    assert listbox.options["selectforeground"] == "#ffffff"
    assert listbox.pack_calls == [{"fill": "both", "expand": True}]
    assert listbox.items == ["first", "second", "third"]
    assert listbox.selection == [1]
    assert listbox.selection_set_calls == [(1, None)]
    assert listbox.activate_calls == [1]
    assert listbox.see_calls == [1]
    assert listbox.focus_set_calls == 1
    assert set(listbox.bound_callbacks) == {
        "<Motion>",
        "<ButtonRelease-1>",
        "<Return>",
        "<Escape>",
        "<FocusOut>",
    }
    assert set(popup.bound_callbacks) == {"<Button-1>"}


def test_open_tolerates_current_selection_restore_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_tk(monkeypatch, listbox_failures={"see": RuntimeError("see failed")})
    widget, _chosen = _make_dropdown(current="second")

    assert widget.open() == "break"

    popup = registry["popup"]
    listbox = registry["listbox"]
    assert isinstance(popup, _FakePopup)
    assert isinstance(listbox, _FakeListbox)
    assert widget.is_open() is True
    assert listbox.selection_set_calls == [(1, None)]
    assert popup.deiconify_calls == 1


def test_open_tolerates_popup_grab_focus_attribute_configure_and_root_bind_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _FakeRoot(bind_error=RuntimeError("bind failed"))
    registry = _install_fake_tk(
        monkeypatch,
        popup_failures={
            "attributes": RuntimeError("attributes failed"),
            "configure": RuntimeError("configure failed"),
            "grab_set": RuntimeError("grab failed"),
            "focus_force": RuntimeError("focus failed"),
        },
    )
    widget, _chosen = _make_dropdown(root=root)

    assert widget.open() == "break"

    popup = registry["popup"]
    listbox = registry["listbox"]
    assert isinstance(popup, _FakePopup)
    assert isinstance(listbox, _FakeListbox)
    assert widget.is_open() is True
    assert popup.attributes_calls == [("-type", "combo")]
    assert popup.configure_calls == [{"bg": "#101010"}]
    assert popup.grab_set_calls == 1
    assert popup.focus_force_calls == 1
    assert root.bind_calls == [("<Destroy>", widget.close, True)]
    assert listbox.focus_set_calls == 1
