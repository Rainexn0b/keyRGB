"""UX-06 final geometry save through each calibrator close route."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from keyrgb.gui.calibrator import _app_logic


class _FakeTracker:
    def __init__(self) -> None:
        self.save_now_calls = 0

    def save_now(self) -> bool:
        self.save_now_calls += 1
        return True


def _make_close_app(*, with_tracker: bool) -> tuple[SimpleNamespace, list[str], _FakeTracker | None]:
    order: list[str] = []
    tracker = _FakeTracker() if with_tracker else None
    app = SimpleNamespace(
        _save=lambda: order.append("save"),
        _restore_original_config=lambda: order.append("restore"),
        destroy=lambda: order.append("destroy"),
    )
    if with_tracker:
        assert tracker is not None
        original_save_now = tracker.save_now

        def _save_now() -> bool:
            order.append("save_now")
            return original_save_now()

        tracker.save_now = _save_now  # type: ignore[method-assign]
        app._window_geometry_tracker = tracker
    return app, order, tracker


def test_on_close_saves_geometry_before_destroy() -> None:
    app, order, tracker = _make_close_app(with_tracker=True)

    _app_logic.on_close(app)

    assert order == ["save_now", "restore", "destroy"]
    assert tracker is not None
    assert tracker.save_now_calls == 1


def test_save_and_close_saves_geometry_before_destroy() -> None:
    app, order, tracker = _make_close_app(with_tracker=True)

    _app_logic.save_and_close(app)

    assert order == ["save", "save_now", "restore", "destroy"]
    assert tracker is not None
    assert tracker.save_now_calls == 1


def test_close_routes_without_tracker_still_destroy() -> None:
    app, order, _tracker = _make_close_app(with_tracker=False)

    _app_logic.on_close(app)
    assert order == ["restore", "destroy"]

    app2, order2, _tracker2 = _make_close_app(with_tracker=False)
    _app_logic.save_and_close(app2)
    assert order2 == ["save", "restore", "destroy"]


def test_unexpected_geometry_save_error_still_restores_and_destroys() -> None:
    order: list[str] = []
    app = SimpleNamespace(
        _window_geometry_tracker=SimpleNamespace(save_now=lambda: (_ for _ in ()).throw(KeyboardInterrupt())),
        _restore_original_config=lambda: order.append("restore"),
        destroy=lambda: order.append("destroy"),
    )

    with pytest.raises(KeyboardInterrupt):
        _app_logic.on_close(app)

    assert order == ["restore", "destroy"]
