from __future__ import annotations

import src.gui.calibrator._app_bootstrap as calibrator_bootstrap


class _FakeApp:
    def __init__(self, *, screen_w: int, screen_h: int, req_w: int, req_h: int) -> None:
        self._screen_w = int(screen_w)
        self._screen_h = int(screen_h)
        self._req_w = int(req_w)
        self._req_h = int(req_h)
        self.update_idletasks_calls = 0
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []

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

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(value)

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((int(width), int(height)))


def test_apply_window_geometry_uses_centered_geometry_helper_and_content_based_minsize(monkeypatch) -> None:
    app = _FakeApp(screen_w=1600, screen_h=1200, req_w=1180, req_h=720)
    seen: dict[str, object] = {}

    def _fake_compute(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return "1400x860+100+120"

    monkeypatch.setattr(calibrator_bootstrap, "compute_centered_window_geometry", _fake_compute)

    calibrator_bootstrap.apply_window_geometry(app)

    assert app.update_idletasks_calls == 1
    assert seen == {
        "root": app,
        "content_height_px": 720,
        "content_width_px": 1180,
        "footer_height_px": 0,
        "chrome_padding_px": 32,
        "default_w": 1400,
        "default_h": 860,
        "screen_ratio_cap": 0.95,
    }
    assert app.geometry_calls == ["1400x860+100+120"]
    assert app.minsize_calls == [(1180, 752)]


def test_apply_window_geometry_clamps_minsize_to_screen_ratio_cap() -> None:
    app = _FakeApp(screen_w=1000, screen_h=900, req_w=2000, req_h=1200)

    calibrator_bootstrap.apply_window_geometry(app)

    assert app.minsize_calls == [(950, 855)]