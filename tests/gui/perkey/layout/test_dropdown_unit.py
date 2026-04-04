from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.widgets.dropdown as dropdown


class _FakeRoot:
    def __init__(self, *, bind_error: Exception | None = None) -> None:
        self._bind_error = bind_error
        self.bind_calls: list[tuple[str, object, object]] = []

    def bind(self, event: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((event, callback, add))
        if self._bind_error is not None:
            raise self._bind_error


class _FakeAnchor:
    def __init__(self, *, x: int = 10, y: int = 100, width: int = 120, height: int = 24) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def winfo_rootx(self) -> int:
        return self._x

    def winfo_rooty(self) -> int:
        return self._y

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height


class _FakePopup:
    def __init__(self, parent: object, *, reqheight: int = 40, failures: dict[str, Exception] | None = None) -> None:
        self.parent = parent
        self.reqheight = reqheight
        self.failures = dict(failures or {})
        self.attributes_calls: list[tuple[object, ...]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.transient_calls: list[object] = []
        self.overrideredirect_calls: list[bool] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.bound_callbacks: dict[str, object] = {}
        self.geometry_calls: list[str] = []
        self.withdraw_calls = 0
        self.update_idletasks_calls = 0
        self.deiconify_calls = 0
        self.lift_calls = 0
        self.grab_set_calls = 0
        self.focus_force_calls = 0
        self.grab_release_calls = 0
        self.destroy_calls = 0

    def _maybe_raise(self, name: str) -> None:
        failure = self.failures.get(name)
        if failure is not None:
            raise failure

    def withdraw(self) -> None:
        self.withdraw_calls += 1

    def transient(self, root: object) -> None:
        self.transient_calls.append(root)

    def overrideredirect(self, value: bool) -> None:
        self.overrideredirect_calls.append(value)

    def attributes(self, *args: object) -> None:
        self.attributes_calls.append(args)
        self._maybe_raise("attributes")

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)
        self._maybe_raise("configure")

    def bind(self, event: str, callback: object) -> None:
        self.bind_calls.append((event, callback))
        self.bound_callbacks[event] = callback
        self._maybe_raise("bind")

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_reqheight(self) -> int:
        return self.reqheight

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def deiconify(self) -> None:
        self.deiconify_calls += 1

    def lift(self) -> None:
        self.lift_calls += 1

    def grab_set(self) -> None:
        self.grab_set_calls += 1
        self._maybe_raise("grab_set")

    def focus_force(self) -> None:
        self.focus_force_calls += 1
        self._maybe_raise("focus_force")

    def grab_release(self) -> None:
        self.grab_release_calls += 1
        self._maybe_raise("grab_release")

    def destroy(self) -> None:
        self.destroy_calls += 1
        self._maybe_raise("destroy")


class _FakeListbox:
    def __init__(self, parent: object, *, failures: dict[str, Exception] | None = None, **kwargs: object) -> None:
        self.parent = parent
        self.options = dict(kwargs)
        self.failures = dict(failures or {})
        self.items: list[str] = []
        self.pack_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.bound_callbacks: dict[str, object] = {}
        self.selection_clear_calls: list[tuple[object, object]] = []
        self.selection_set_calls: list[tuple[object, object | None]] = []
        self.activate_calls: list[int] = []
        self.see_calls: list[int] = []
        self.selection: list[int] = []
        self.nearest_result = 0
        self.focus_set_calls = 0

    def _maybe_raise(self, name: str) -> None:
        failure = self.failures.get(name)
        if failure is not None:
            raise failure

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(kwargs)

    def insert(self, _where: object, value: str) -> None:
        self.items.append(value)

    def selection_set(self, index: object, last: object = None) -> None:
        self.selection_set_calls.append((index, last))
        self._maybe_raise("selection_set")
        self.selection = [int(index)]

    def activate(self, index: int) -> None:
        self.activate_calls.append(index)
        self._maybe_raise("activate")

    def see(self, index: int) -> None:
        self.see_calls.append(index)
        self._maybe_raise("see")

    def curselection(self) -> tuple[int, ...]:
        self._maybe_raise("curselection")
        return tuple(self.selection)

    def get(self, index: int) -> str:
        self._maybe_raise("get")
        return self.items[index]

    def nearest(self, _y: int) -> int:
        self._maybe_raise("nearest")
        return self.nearest_result

    def selection_clear(self, first: object, last: object) -> None:
        self.selection_clear_calls.append((first, last))
        self._maybe_raise("selection_clear")
        self.selection = []

    def bind(self, event: str, callback: object) -> None:
        self.bind_calls.append((event, callback))
        self.bound_callbacks[event] = callback

    def focus_set(self) -> None:
        self.focus_set_calls += 1


def _install_fake_tk(
    monkeypatch: pytest.MonkeyPatch,
    *,
    prefers_dark: bool | None = None,
    popup_failures: dict[str, Exception] | None = None,
    listbox_failures: dict[str, Exception] | None = None,
    popup_reqheight: int = 40,
) -> dict[str, object]:
    registry: dict[str, object] = {"popup_count": 0, "listbox_count": 0}

    def fake_toplevel(root: object) -> _FakePopup:
        popup = _FakePopup(root, reqheight=popup_reqheight, failures=popup_failures)
        registry["popup"] = popup
        registry["popup_count"] = int(registry["popup_count"]) + 1
        return popup

    def fake_listbox(parent: object, **kwargs: object) -> _FakeListbox:
        listbox = _FakeListbox(parent, failures=listbox_failures, **kwargs)
        registry["listbox"] = listbox
        registry["listbox_count"] = int(registry["listbox_count"]) + 1
        return listbox

    monkeypatch.setattr(dropdown.tk, "Toplevel", fake_toplevel)
    monkeypatch.setattr(dropdown.tk, "Listbox", fake_listbox)
    monkeypatch.setattr(dropdown, "detect_system_prefers_dark", lambda: prefers_dark)
    return registry


def _make_dropdown(
    *,
    root: _FakeRoot | None = None,
    anchor: _FakeAnchor | None = None,
    values: tuple[str, ...] = ("first", "second", "third"),
    current: str = "",
) -> tuple[dropdown.UpwardListboxDropdown, list[str]]:
    chosen: list[str] = []
    widget = dropdown.UpwardListboxDropdown(
        root or _FakeRoot(),
        anchor or _FakeAnchor(),
        lambda: values,
        lambda: current,
        lambda value: chosen.append(value),
        "#101010",
        "#efefef",
    )
    return widget, chosen


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
