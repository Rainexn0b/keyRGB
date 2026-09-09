"""UX-06 window-geometry integration for the keymap calibrator."""

from __future__ import annotations

import pytest

from keyrgb.gui.calibrator import _app_bootstrap as calibrator_bootstrap


class _FakeTracker:
    last_instance: _FakeTracker | None = None

    def __init__(
        self,
        root: object,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> None:
        self.root = root
        self.window_id = window_id
        self.min_width = int(min_width)
        self.min_height = int(min_height)
        self.screen_ratio_cap = float(screen_ratio_cap)
        self.debounce_ms = int(debounce_ms)
        self.restore_result = False
        self.restore_calls = 0
        self.start_tracking_calls = 0
        self.save_now_calls = 0
        _FakeTracker.last_instance = self

    def restore(self) -> bool:
        self.restore_calls += 1
        if self.restore_result:
            self.root.geometry("1000x750+11+22")  # type: ignore[union-attr]
        return self.restore_result

    def start_tracking(self) -> None:
        self.start_tracking_calls += 1

    def save_now(self) -> bool:
        self.save_now_calls += 1
        return True


class _FakeApp:
    def __init__(self, *, screen_w: int, screen_h: int, req_w: int, req_h: int) -> None:
        self._screen_w = int(screen_w)
        self._screen_h = int(screen_h)
        self._req_w = int(req_w)
        self._req_h = int(req_h)
        self.update_idletasks_calls = 0
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []
        self.after_calls: list[tuple[int, object]] = []
        self.calls: list[str] = []

    def update_idletasks(self) -> None:
        self.update_idletasks_calls += 1

    def winfo_screenwidth(self) -> int:
        return self._screen_w

    def winfo_screenheight(self) -> int:
        return self._screen_h

    def winfo_reqwidth(self) -> int:
        return self._req_w

    def winfo_reqheight(self) -> int:
        return self._req_h

    def winfo_width(self) -> int:
        return 1000

    def winfo_height(self) -> int:
        return 750

    def winfo_x(self) -> int:
        return 11

    def winfo_y(self) -> int:
        return 22

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(str(value))

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((int(width), int(height)))

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.calls.append(f"bind:{sequence}")

    def after(self, delay_ms: int, callback: object) -> str:
        self.after_calls.append((delay_ms, callback))
        return "after1"

    def after_cancel(self, after_id: object) -> None:
        self.calls.append("after_cancel")


def _install_tracker(monkeypatch: pytest.MonkeyPatch, *, restore_result: bool) -> None:
    def _factory(
        root: object,
        window_id: str,
        min_width: int,
        min_height: int,
        screen_ratio_cap: float = 0.95,
        debounce_ms: int = 500,
    ) -> _FakeTracker:
        tracker = _FakeTracker(root, window_id, min_width, min_height, screen_ratio_cap, debounce_ms)
        tracker.restore_result = restore_result
        return tracker

    monkeypatch.setattr(calibrator_bootstrap, "WindowGeometryTracker", _factory)


def test_tracker_wired_with_calibrator_identity_computed_minimum_and_screen_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeTracker.last_instance = None
    _install_tracker(monkeypatch, restore_result=False)
    app = _FakeApp(screen_w=1600, screen_h=1200, req_w=1180, req_h=720)

    assert calibrator_bootstrap.apply_window_geometry(app) is False

    tracker = _FakeTracker.last_instance
    assert tracker is not None
    assert tracker.root is app
    assert tracker.window_id == "calibrator"
    assert (tracker.min_width, tracker.min_height) == (1180, 752)
    assert tracker.screen_ratio_cap == pytest.approx(0.95)
    assert app._window_geometry_tracker is tracker


def test_restore_true_skips_centered_fallback_but_keeps_minsize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_tracker(monkeypatch, restore_result=True)
    app = _FakeApp(screen_w=1600, screen_h=1200, req_w=1180, req_h=720)

    assert calibrator_bootstrap.apply_window_geometry(app) is True

    # Restored geometry survives: no centered fallback overwrite.
    assert app.geometry_calls == ["1000x750+11+22"]
    assert app.minsize_calls == [(1180, 752)]


def test_restore_false_preserves_exact_centered_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_tracker(monkeypatch, restore_result=False)
    app = _FakeApp(screen_w=1600, screen_h=1200, req_w=1180, req_h=720)

    assert calibrator_bootstrap.apply_window_geometry(app) is False

    assert app.update_idletasks_calls == 1
    assert len(app.geometry_calls) == 1
    assert app.geometry_calls[0].startswith("1400x860+")
    assert app.minsize_calls == [(1180, 752)]


def test_finish_init_starts_tracking_after_deiconify_callbacks() -> None:
    order: list[str] = []
    scheduled: list[tuple[int, object]] = []
    tracker = _FakeTracker(object(), "calibrator", 1100, 650)

    def _start_tracking() -> None:
        order.append("start_tracking")
        _FakeTracker.start_tracking(tracker)

    tracker.start_tracking = _start_tracking  # type: ignore[method-assign]

    class _AppFinish:
        def _load_deck_image(self) -> None:
            order.append("load")

        def _apply_current_probe(self) -> None:
            order.append("probe")

        def _redraw(self) -> None:
            order.append("redraw")

        def deiconify(self) -> None:
            order.append("deiconify")

        def lift(self) -> None:
            order.append("lift")

        def after(self, delay_ms: int, callback: object) -> None:
            scheduled.append((delay_ms, callback))

    app = _AppFinish()
    app._window_geometry_tracker = tracker  # type: ignore[attr-defined]

    calibrator_bootstrap.finish_init(app, tk_runtime_errors=(RuntimeError,))

    assert [delay for delay, _callback in scheduled] == [0]
    scheduled.pop(0)[1]()
    assert order == ["load", "probe", "redraw", "deiconify", "lift"]
    assert [delay for delay, _callback in scheduled] == [50]
    assert tracker.start_tracking_calls == 0
    scheduled.pop(0)[1]()
    assert order == ["load", "probe", "redraw", "deiconify", "lift", "start_tracking"]
    assert tracker.start_tracking_calls == 1


def test_finish_init_starts_tracking_despite_deiconify_errors() -> None:
    order: list[str] = []
    scheduled: list[tuple[int, object]] = []
    tracker = _FakeTracker(object(), "calibrator", 1100, 650)

    def _start_tracking() -> None:
        order.append("start_tracking")
        _FakeTracker.start_tracking(tracker)

    tracker.start_tracking = _start_tracking  # type: ignore[method-assign]

    class _AppFinish:
        def _load_deck_image(self) -> None:
            order.append("load")

        def _apply_current_probe(self) -> None:
            order.append("probe")

        def _redraw(self) -> None:
            order.append("redraw")

        def deiconify(self) -> None:
            raise RuntimeError("no window")

        def lift(self) -> None:
            order.append("lift")

        def after(self, delay_ms: int, callback: object) -> None:
            scheduled.append((delay_ms, callback))

    app = _AppFinish()
    app._window_geometry_tracker = tracker  # type: ignore[attr-defined]

    calibrator_bootstrap.finish_init(app, tk_runtime_errors=(RuntimeError,))

    # lift() is skipped with deiconify() inside the guarded block, but
    # tracking still starts so geometry keeps persisting.
    scheduled.pop(0)[1]()
    assert [delay for delay, _callback in scheduled] == [50]
    assert order == ["load", "probe", "redraw"]
    scheduled.pop(0)[1]()
    assert order == ["load", "probe", "redraw", "start_tracking"]


def test_finish_init_without_tracker_still_runs_startup_callbacks() -> None:
    order: list[str] = []

    class _AppFinish:
        def _load_deck_image(self) -> None:
            order.append("load")

        def _apply_current_probe(self) -> None:
            order.append("probe")

        def _redraw(self) -> None:
            order.append("redraw")

        def deiconify(self) -> None:
            order.append("deiconify")

        def lift(self) -> None:
            order.append("lift")

        def after(self, delay_ms: int, callback: object) -> None:
            callback()

    calibrator_bootstrap.finish_init(_AppFinish(), tk_runtime_errors=(RuntimeError,))

    assert order == ["load", "probe", "redraw", "deiconify", "lift"]
