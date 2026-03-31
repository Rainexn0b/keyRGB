from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.scrollable_area as scrollable_area


class _FakeCanvas:
    def __init__(
        self,
        *,
        bbox_result: tuple[int, int, int, int] | None = None,
        height: int = 100,
        bbox_error: Exception | None = None,
        yview_error: Exception | None = None,
    ) -> None:
        self._bbox_result = bbox_result
        self._height = height
        self._bbox_error = bbox_error
        self._yview_error = yview_error
        self.yview_scroll_calls: list[tuple[int, str]] = []

    def bbox(self, tag: str) -> tuple[int, int, int, int] | None:
        assert tag == "all"
        if self._bbox_error is not None:
            raise self._bbox_error
        return self._bbox_result

    def winfo_height(self) -> int:
        return self._height

    def yview_scroll(self, units: int, what: str) -> None:
        self.yview_scroll_calls.append((units, what))
        if self._yview_error is not None:
            raise self._yview_error


class _FakeScrollbar:
    def __init__(
        self,
        *,
        pack_error: Exception | None = None,
        pack_forget_error: Exception | None = None,
    ) -> None:
        self._pack_error = pack_error
        self._pack_forget_error = pack_forget_error
        self.pack_calls: list[dict[str, str]] = []
        self.pack_forget_calls = 0

    def pack(self, **kwargs: str) -> None:
        self.pack_calls.append(dict(kwargs))
        if self._pack_error is not None:
            raise self._pack_error

    def pack_forget(self) -> None:
        self.pack_forget_calls += 1
        if self._pack_forget_error is not None:
            raise self._pack_forget_error


class _FakeWidget:
    def __init__(
        self,
        *,
        master: object | None = None,
        toplevel: object | None = None,
        yview_error: Exception | None = None,
    ) -> None:
        self.master = master
        self._toplevel = toplevel
        self._yview_error = yview_error
        self.yview_scroll_calls: list[tuple[int, str]] = []

    def winfo_toplevel(self) -> object:
        return self._toplevel if self._toplevel is not None else self

    def yview_scroll(self, units: int, what: str) -> None:
        self.yview_scroll_calls.append((units, what))
        if self._yview_error is not None:
            raise self._yview_error


class _BrokenMasterWidget:
    @property
    def master(self) -> object:
        raise RuntimeError("boom")


class _FakeRoot:
    def __init__(
        self,
        *,
        target: object | None = None,
        containing_error: Exception | None = None,
    ) -> None:
        self._target = target
        self._containing_error = containing_error
        self.bind_all_calls: list[tuple[str, object]] = []
        self.bound_callbacks: dict[str, object] = {}
        self.containing_calls: list[tuple[int, int]] = []

    def bind_all(self, event: str, callback: object) -> None:
        self.bind_all_calls.append((event, callback))
        self.bound_callbacks[event] = callback

    def winfo_containing(self, x_root: int, y_root: int) -> object | None:
        self.containing_calls.append((x_root, y_root))
        if self._containing_error is not None:
            raise self._containing_error
        return self._target


def _make_area(
    *,
    canvas: _FakeCanvas | None = None,
    scrollbar: _FakeScrollbar | None = None,
    vscroll_visible: bool = True,
) -> scrollable_area.ScrollableArea:
    area = scrollable_area.ScrollableArea.__new__(scrollable_area.ScrollableArea)
    area._canvas = canvas or _FakeCanvas()
    area._vscroll = scrollbar or _FakeScrollbar()
    area._vscroll_visible = vscroll_visible
    return area


@pytest.mark.parametrize(
    ("bbox_result", "height", "expected"),
    [
        (None, 100, False),
        ((0, 0, 10, 2), 0, True),
        ((0, 0, 10, 40), 40, False),
        ((0, 0, 10, 41), 40, True),
    ],
)
def test_content_needs_scroll_uses_bbox_and_canvas_height(
    bbox_result: tuple[int, int, int, int] | None,
    height: int,
    expected: bool,
) -> None:
    area = _make_area(canvas=_FakeCanvas(bbox_result=bbox_result, height=height))

    assert area._content_needs_scroll() is expected


def test_content_needs_scroll_returns_false_when_canvas_probe_fails() -> None:
    area = _make_area(canvas=_FakeCanvas(bbox_error=RuntimeError("bbox failed")))

    assert area._content_needs_scroll() is False


def test_update_scrollbar_visibility_toggles_hidden_and_visible_states() -> None:
    canvas = _FakeCanvas(bbox_result=(0, 0, 10, 40), height=80)
    scrollbar = _FakeScrollbar()
    area = _make_area(canvas=canvas, scrollbar=scrollbar, vscroll_visible=True)

    area._update_scrollbar_visibility()

    assert area._vscroll_visible is False
    assert scrollbar.pack_forget_calls == 1

    canvas._bbox_result = (0, 0, 10, 120)

    area._update_scrollbar_visibility()

    assert area._vscroll_visible is True
    assert scrollbar.pack_calls == [{"side": "right", "fill": "y"}]


def test_update_scrollbar_visibility_swallows_scrollbar_pack_errors() -> None:
    area = _make_area(
        canvas=_FakeCanvas(bbox_result=(0, 0, 10, 120), height=40),
        scrollbar=_FakeScrollbar(pack_error=RuntimeError("pack failed")),
        vscroll_visible=False,
    )

    area._update_scrollbar_visibility()

    assert area._vscroll_visible is False
    assert area._vscroll.pack_calls == [{"side": "right", "fill": "y"}]


def test_is_descendant_walks_master_chain_and_handles_broken_master_access() -> None:
    ancestor = _FakeWidget()
    middle = _FakeWidget(master=ancestor)
    child = _FakeWidget(master=middle)

    assert scrollable_area.ScrollableArea._is_descendant(child, ancestor) is True
    assert scrollable_area.ScrollableArea._is_descendant(_FakeWidget(), ancestor) is False
    assert scrollable_area.ScrollableArea._is_descendant(_BrokenMasterWidget(), ancestor) is False


def test_finalize_initial_scrollbar_state_hides_scrollbar_when_content_fits() -> None:
    scrollbar = _FakeScrollbar()
    area = _make_area(
        canvas=_FakeCanvas(bbox_result=(0, 0, 10, 60), height=120),
        scrollbar=scrollbar,
        vscroll_visible=True,
    )

    area.finalize_initial_scrollbar_state()

    assert area._vscroll_visible is False
    assert scrollbar.pack_forget_calls == 1


def test_finalize_initial_scrollbar_state_leaves_visible_scrollbar_when_needed_or_unavailable() -> None:
    needed_scrollbar = _FakeScrollbar()
    area = _make_area(
        canvas=_FakeCanvas(bbox_result=(0, 0, 10, 160), height=80),
        scrollbar=needed_scrollbar,
        vscroll_visible=True,
    )

    area.finalize_initial_scrollbar_state()

    assert area._vscroll_visible is True
    assert needed_scrollbar.pack_forget_calls == 0

    missing_bbox_scrollbar = _FakeScrollbar()
    missing_bbox_area = _make_area(
        canvas=_FakeCanvas(bbox_result=None, height=80),
        scrollbar=missing_bbox_scrollbar,
        vscroll_visible=True,
    )

    missing_bbox_area.finalize_initial_scrollbar_state()

    assert missing_bbox_area._vscroll_visible is True
    assert missing_bbox_scrollbar.pack_forget_calls == 0


def test_bind_mousewheel_registers_handlers_and_prioritizes_descendant_widget() -> None:
    root = _FakeRoot()
    priority = _FakeWidget(toplevel=root)
    target = _FakeWidget(master=priority, toplevel=root)
    root._target = target
    canvas = _FakeCanvas(bbox_result=(0, 0, 10, 300), height=80)
    area = _make_area(canvas=canvas)

    area.bind_mousewheel(root, priority_scroll_widget=priority)

    assert [event for event, _callback in root.bind_all_calls] == ["<MouseWheel>", "<Button-4>", "<Button-5>"]

    callback = root.bound_callbacks["<MouseWheel>"]
    result = callback(SimpleNamespace(x_root=10, y_root=20, delta=120))

    assert result == "break"
    assert priority.yview_scroll_calls == [(-1, "units")]
    assert canvas.yview_scroll_calls == []


def test_bind_mousewheel_routes_button_events_to_canvas_when_content_needs_scroll() -> None:
    root = _FakeRoot()
    root._target = _FakeWidget(toplevel=root)
    canvas = _FakeCanvas(bbox_result=(0, 0, 10, 300), height=80)
    area = _make_area(canvas=canvas)

    area.bind_mousewheel(root)

    up = root.bound_callbacks["<Button-4>"]
    down = root.bound_callbacks["<Button-5>"]

    assert up(SimpleNamespace(x_root=1, y_root=2, num=4)) == "break"
    assert down(SimpleNamespace(x_root=1, y_root=2, num=5)) == "break"
    assert canvas.yview_scroll_calls == [(-1, "units"), (1, "units")]


def test_bind_mousewheel_returns_none_when_no_target_or_no_scroll_units() -> None:
    root = _FakeRoot(target=None)
    area = _make_area(canvas=_FakeCanvas(bbox_result=(0, 0, 10, 300), height=80))

    area.bind_mousewheel(root)

    callback = root.bound_callbacks["<MouseWheel>"]

    assert callback(SimpleNamespace(x_root=5, y_root=6, delta=120)) is None

    root._target = _FakeWidget(toplevel=root)

    assert callback(SimpleNamespace(x_root=5, y_root=6, delta=0)) is None
    assert area._canvas.yview_scroll_calls == []


def test_bind_mousewheel_swallows_lookup_and_scroll_failures() -> None:
    lookup_root = _FakeRoot(containing_error=RuntimeError("lookup failed"))
    lookup_area = _make_area(canvas=_FakeCanvas(bbox_result=(0, 0, 10, 300), height=80))
    lookup_area.bind_mousewheel(lookup_root)

    lookup_callback = lookup_root.bound_callbacks["<MouseWheel>"]

    assert lookup_callback(SimpleNamespace(x_root=1, y_root=2, delta=120)) is None

    priority_root = _FakeRoot()
    broken_priority = _FakeWidget(toplevel=priority_root, yview_error=RuntimeError("priority failed"))
    priority_root._target = _FakeWidget(master=broken_priority, toplevel=priority_root)
    priority_area = _make_area(canvas=_FakeCanvas(bbox_result=(0, 0, 10, 300), height=80))
    priority_area.bind_mousewheel(priority_root, priority_scroll_widget=broken_priority)

    priority_callback = priority_root.bound_callbacks["<MouseWheel>"]

    assert priority_callback(SimpleNamespace(x_root=1, y_root=2, delta=120)) is None

    canvas_root = _FakeRoot()
    canvas_root._target = _FakeWidget(toplevel=canvas_root)
    canvas_area = _make_area(
        canvas=_FakeCanvas(
            bbox_result=(0, 0, 10, 300),
            height=80,
            yview_error=RuntimeError("canvas failed"),
        )
    )
    canvas_area.bind_mousewheel(canvas_root)

    canvas_callback = canvas_root.bound_callbacks["<MouseWheel>"]

    assert canvas_callback(SimpleNamespace(x_root=1, y_root=2, delta=120)) is None
    assert canvas_area._canvas.yview_scroll_calls == [(-1, "units")]