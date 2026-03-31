from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.perkey.canvas_impl._canvas_events as canvas_events
from src.gui.perkey.canvas_impl._canvas_events import _KeyboardCanvasEventMixin


class _FakeVar:
    def __init__(self, value: str, *, exc: Exception | None = None) -> None:
        self.value = value
        self.exc = exc

    def get(self) -> str:
        if self.exc is not None:
            raise self.exc
        return self.value


class _FakeEditor:
    def __init__(self, *, scope: str = "key", selected_key_id: str | None = "k1") -> None:
        self.overlay_scope = _FakeVar(scope)
        self.selected_key_id = selected_key_id
        self.clicked_keys: list[str] = []

    def on_key_clicked(self, key_id: str) -> None:
        self.clicked_keys.append(str(key_id))


class _FakeCanvas(_KeyboardCanvasEventMixin):
    def __init__(self, *, scope: str = "key", selected_key_id: str | None = "k1") -> None:
        self.editor = _FakeEditor(scope=scope, selected_key_id=selected_key_id)
        self._resize_job: str | None = None

        self.after_cancel_error: Exception | None = None
        self.configure_error: Exception | None = None
        self.resize_edges_error: Exception | None = None
        self.find_withtag_error: Exception | None = None
        self.gettags_error: Exception | None = None

        self.cancel_calls: list[str] = []
        self.after_calls: list[tuple[int, object]] = []
        self.configure_calls: list[str] = []
        self.redraw_calls = 0
        self.resize_edge_calls: list[tuple[str, float, float]] = []
        self.cursor_for_edges_calls: list[str] = []
        self.point_in_key_bbox_calls: list[tuple[str, float, float]] = []
        self.find_withtag_calls: list[str] = []
        self.gettags_calls: list[int] = []
        self.hit_test_calls: list[tuple[float, float]] = []

        self.resize_edges_result = ""
        self.cursor_for_edges_result = "edge-cursor"
        self.point_in_key_bbox_result = False
        self.current_items: tuple[int, ...] = ()
        self.tags_by_item: dict[int, tuple[str, ...]] = {}
        self.hit_test_result: str | None = None

    def after_cancel(self, job: str) -> None:
        self.cancel_calls.append(job)
        if self.after_cancel_error is not None:
            raise self.after_cancel_error

    def after(self, delay_ms: int, callback) -> str:
        self.after_calls.append((int(delay_ms), callback))
        return "job-new"

    def redraw(self) -> None:
        self.redraw_calls += 1

    def configure(self, *, cursor: str) -> None:
        self.configure_calls.append(str(cursor))
        if self.configure_error is not None:
            raise self.configure_error

    def _resize_edges_for_point(self, key_id: str, cx: float, cy: float) -> str:
        self.resize_edge_calls.append((str(key_id), float(cx), float(cy)))
        if self.resize_edges_error is not None:
            raise self.resize_edges_error
        return self.resize_edges_result

    def _cursor_for_edges(self, edges: str) -> str:
        self.cursor_for_edges_calls.append(str(edges))
        return self.cursor_for_edges_result

    def _point_in_key_bbox(self, key_id: str, cx: float, cy: float) -> bool:
        self.point_in_key_bbox_calls.append((str(key_id), float(cx), float(cy)))
        return self.point_in_key_bbox_result

    def find_withtag(self, tag: str) -> tuple[int, ...]:
        self.find_withtag_calls.append(str(tag))
        if self.find_withtag_error is not None:
            raise self.find_withtag_error
        return self.current_items

    def gettags(self, item: int) -> tuple[str, ...]:
        self.gettags_calls.append(int(item))
        if self.gettags_error is not None:
            raise self.gettags_error
        return self.tags_by_item.get(item, ())

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        self.hit_test_calls.append((float(cx), float(cy)))
        return self.hit_test_result


def _event(*, x: float = 10, y: float = 20) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def _capture_logs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[tuple[object, ...], dict[str, object]]]:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_log_throttled(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(canvas_events, "log_throttled", fake_log_throttled)
    return calls


def test_on_resize_cancels_existing_job_and_schedules_redraw() -> None:
    canvas = _FakeCanvas()
    canvas._resize_job = "job-old"

    canvas._on_resize(_event())

    assert canvas.cancel_calls == ["job-old"]
    assert len(canvas.after_calls) == 1
    delay_ms, callback = canvas.after_calls[0]
    assert delay_ms == 40
    assert callback.__self__ is canvas
    assert callback.__func__ is _KeyboardCanvasEventMixin._redraw_callback
    assert canvas._resize_job == "job-new"


def test_on_resize_logs_after_cancel_failures_and_still_schedules_redraw(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas._resize_job = "job-old"
    canvas.after_cancel_error = RuntimeError("boom")
    logs = _capture_logs(monkeypatch)

    canvas._on_resize(_event())

    assert canvas.cancel_calls == ["job-old"]
    assert canvas._resize_job == "job-new"
    assert [delay for delay, _ in canvas.after_calls] == [40]
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.canvas.after_cancel"
    assert kwargs["msg"] == "after_cancel failed"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_redraw_callback_clears_resize_job_and_redraws() -> None:
    canvas = _FakeCanvas()
    canvas._resize_job = "job-old"

    canvas._redraw_callback()

    assert canvas._resize_job is None
    assert canvas.redraw_calls == 1


def test_on_motion_clears_cursor_when_overlay_scope_is_not_key() -> None:
    canvas = _FakeCanvas(scope="global", selected_key_id="k1")

    canvas._on_motion(_event(x=11, y=22))

    assert canvas.configure_calls == [""]
    assert canvas.resize_edge_calls == []
    assert canvas.point_in_key_bbox_calls == []


def test_on_motion_uses_resize_cursor_when_pointer_is_on_resize_edge() -> None:
    canvas = _FakeCanvas(scope="key", selected_key_id="k1")
    canvas.resize_edges_result = "rb"
    canvas.cursor_for_edges_result = "top_left_corner"

    canvas._on_motion(_event(x=5, y=7))

    assert canvas.resize_edge_calls == [("k1", 5.0, 7.0)]
    assert canvas.cursor_for_edges_calls == ["rb"]
    assert canvas.point_in_key_bbox_calls == []
    assert canvas.configure_calls == ["top_left_corner"]


def test_on_motion_uses_move_cursor_inside_selected_key() -> None:
    canvas = _FakeCanvas(scope="key", selected_key_id="k1")
    canvas.point_in_key_bbox_result = True

    canvas._on_motion(_event(x=15, y=17))

    assert canvas.resize_edge_calls == [("k1", 15.0, 17.0)]
    assert canvas.point_in_key_bbox_calls == [("k1", 15.0, 17.0)]
    assert canvas.configure_calls == ["fleur"]


def test_on_motion_clears_cursor_outside_selected_key() -> None:
    canvas = _FakeCanvas(scope="key", selected_key_id="k1")
    canvas.point_in_key_bbox_result = False

    canvas._on_motion(_event(x=25, y=27))

    assert canvas.resize_edge_calls == [("k1", 25.0, 27.0)]
    assert canvas.point_in_key_bbox_calls == [("k1", 25.0, 27.0)]
    assert canvas.configure_calls == [""]


def test_on_motion_logs_and_swallows_hover_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas(scope="key", selected_key_id="k1")
    canvas.editor.overlay_scope = _FakeVar("key", exc=RuntimeError("boom"))
    logs = _capture_logs(monkeypatch)

    canvas._on_motion(_event())

    assert canvas.configure_calls == []
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.canvas.on_motion"
    assert kwargs["msg"] == "Error in perkey hover handling"


def test_on_leave_resets_cursor() -> None:
    canvas = _FakeCanvas()

    canvas._on_leave(_event())

    assert canvas.configure_calls == [""]


def test_on_leave_logs_configure_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas = _FakeCanvas()
    canvas.configure_error = RuntimeError("no cursor")
    logs = _capture_logs(monkeypatch)

    canvas._on_leave(_event())

    assert canvas.configure_calls == [""]
    assert len(logs) == 1
    args, kwargs = logs[0]
    assert args[1] == "perkey.canvas.on_leave"
    assert kwargs["msg"] == "Error resetting cursor"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_on_click_uses_current_item_pkey_tag_before_hit_test() -> None:
    canvas = _FakeCanvas()
    canvas.current_items = (7,)
    canvas.tags_by_item = {7: ("overlay", "pkey_enter")}

    canvas._on_click(_event(x=3, y=4))

    assert canvas.find_withtag_calls == ["current"]
    assert canvas.gettags_calls == [7]
    assert canvas.editor.clicked_keys == ["enter"]
    assert canvas.hit_test_calls == []


def test_on_click_falls_back_to_hit_test_when_current_item_has_no_key_tag() -> None:
    canvas = _FakeCanvas()
    canvas.current_items = (9,)
    canvas.tags_by_item = {9: ("overlay", "selected")}
    canvas.hit_test_result = "esc"

    canvas._on_click(_event(x=8, y=12))

    assert canvas.find_withtag_calls == ["current"]
    assert canvas.gettags_calls == [9]
    assert canvas.hit_test_calls == [(8.0, 12.0)]
    assert canvas.editor.clicked_keys == ["esc"]