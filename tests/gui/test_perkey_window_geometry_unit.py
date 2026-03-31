from __future__ import annotations

from src.gui.perkey.window_geometry import apply_perkey_editor_geometry


class _FakeRoot:
    def __init__(self, *, screen_w: int, screen_h: int) -> None:
        self._screen_w = int(screen_w)
        self._screen_h = int(screen_h)
        self.geometry_calls: list[str] = []
        self.minsize_calls: list[tuple[int, int]] = []

    def winfo_screenwidth(self) -> int:
        return self._screen_w

    def winfo_screenheight(self) -> int:
        return self._screen_h

    def geometry(self, value: str) -> None:
        self.geometry_calls.append(str(value))

    def minsize(self, width: int, height: int) -> None:
        self.minsize_calls.append((int(width), int(height)))


def _expected_sizes(
    *,
    num_rows: int,
    num_cols: int,
    key_margin: int,
    key_size: int,
    key_gap: int,
    right_panel_width: int,
    wheel_size: int,
    screen_w: int,
    screen_h: int,
) -> tuple[int, int, int, int]:
    keyboard_w = (key_margin * 2) + (num_cols * key_size) + ((num_cols - 1) * key_gap)
    keyboard_h = (key_margin * 2) + (num_rows * key_size) + ((num_rows - 1) * key_gap)

    chrome_w = (16 * 2) + 16
    chrome_h = (16 * 2) + 80

    w0 = keyboard_w + right_panel_width + chrome_w
    h0 = max(keyboard_h + chrome_h, wheel_size + 480)

    max_w = int(screen_w * 0.92)
    max_h = int(screen_h * 0.92)

    w = min(int(w0 * 1.5), max_w)
    h = min(int(h0 * 1.5), max_h)
    return w0, h0, w, h


def test_apply_perkey_editor_geometry_uses_keyboard_math_chrome_padding_and_scaling() -> None:
    root = _FakeRoot(screen_w=2000, screen_h=1600)

    params = dict(
        num_rows=12,
        num_cols=16,
        key_margin=12,
        key_size=32,
        key_gap=4,
        right_panel_width=280,
        wheel_size=60,
    )

    apply_perkey_editor_geometry(root, **params)

    w0, h0, w, h = _expected_sizes(screen_w=2000, screen_h=1600, **params)

    assert (w0, h0) == (924, 564)
    assert (w, h) == (1386, 846)
    assert root.geometry_calls == ["1386x846"]
    assert root.minsize_calls == [(924, 564)]


def test_apply_perkey_editor_geometry_includes_right_panel_width_in_window_width() -> None:
    base_params = dict(
        num_rows=12,
        num_cols=16,
        key_margin=12,
        key_size=32,
        key_gap=4,
        wheel_size=60,
    )

    no_panel_root = _FakeRoot(screen_w=2000, screen_h=1600)
    with_panel_root = _FakeRoot(screen_w=2000, screen_h=1600)

    apply_perkey_editor_geometry(no_panel_root, right_panel_width=0, **base_params)
    apply_perkey_editor_geometry(with_panel_root, right_panel_width=280, **base_params)

    no_panel_width = int(no_panel_root.geometry_calls[0].split("x", 1)[0])
    with_panel_width = int(with_panel_root.geometry_calls[0].split("x", 1)[0])

    assert no_panel_root.minsize_calls == [(644, 564)]
    assert with_panel_root.minsize_calls == [(924, 564)]
    assert with_panel_width - no_panel_width == 420


def test_apply_perkey_editor_geometry_uses_wheel_height_minimum_when_taller() -> None:
    root = _FakeRoot(screen_w=2000, screen_h=1500)

    params = dict(
        num_rows=4,
        num_cols=6,
        key_margin=8,
        key_size=24,
        key_gap=3,
        right_panel_width=180,
        wheel_size=240,
    )

    apply_perkey_editor_geometry(root, **params)

    w0, h0, w, h = _expected_sizes(screen_w=2000, screen_h=1500, **params)

    assert (w0, h0) == (403, 720)
    assert (w, h) == (604, 1080)
    assert root.geometry_calls == ["604x1080"]
    assert root.minsize_calls == [(403, 720)]


def test_apply_perkey_editor_geometry_clamps_to_ninety_two_percent_of_screen() -> None:
    root = _FakeRoot(screen_w=1000, screen_h=900)

    params = dict(
        num_rows=20,
        num_cols=30,
        key_margin=20,
        key_size=40,
        key_gap=5,
        right_panel_width=500,
        wheel_size=200,
    )

    apply_perkey_editor_geometry(root, **params)

    w0, h0, w, h = _expected_sizes(screen_w=1000, screen_h=900, **params)

    assert w0 == 1933
    assert h0 == 1047
    assert (w, h) == (920, 828)
    assert root.geometry_calls == ["920x828"]
    assert root.minsize_calls == [(920, 828)]
