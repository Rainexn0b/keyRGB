"""Shared fakes for dropdown unit-test modules."""

from __future__ import annotations

import pytest

from keyrgb.gui.widgets import dropdown


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
