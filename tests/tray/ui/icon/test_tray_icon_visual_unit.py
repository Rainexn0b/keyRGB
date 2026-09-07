from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar


def test_icon_visual_reactive_uses_base_mosaic_when_manual_color_disabled() -> None:
    from keyrgb.tray.ui.icon import icon_visual

    cfg = SimpleNamespace(
        effect="reactive_fade",
        brightness=20,
        perkey_brightness=20,
        color=(255, 255, 255),
        reactive_color=(255, 0, 0),
        reactive_use_manual_color=False,
        per_key_colors={
            (0, 0): (255, 0, 0),
            (0, 1): (0, 255, 0),
        },
    )

    visual = icon_visual(config=cfg, is_off=False, now=0.0)
    assert visual.mode == "mosaic"
    assert visual.colors_flat is not None
    assert visual.rows > 0
    assert visual.cols > 0


def test_icon_visual_reactive_uses_effect_color_when_manual_color_enabled() -> None:
    from keyrgb.tray.ui.icon import icon_visual

    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=10,
        perkey_brightness=10,
        color=(10, 20, 30),
        reactive_color=(200, 100, 50),
        reactive_use_manual_color=True,
        per_key_colors={
            (0, 0): (255, 0, 0),
            (0, 1): (0, 255, 0),
        },
    )

    visual = icon_visual(config=cfg, is_off=False, now=0.0)
    assert visual.mode == "solid"
    assert visual.color == (120, 60, 30)


def test_icon_visual_reactive_ripple_uses_animated_rainbow_when_manual_color_disabled() -> None:
    from keyrgb.tray.ui.icon import icon_visual

    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=10,
        perkey_brightness=10,
        color=(10, 20, 30),
        reactive_color=(200, 100, 50),
        reactive_use_manual_color=False,
        per_key_colors={(0, 0): (255, 0, 0)},
    )

    visual = icon_visual(config=cfg, is_off=False, now=0.0)
    assert visual.mode == "rainbow"
    assert visual.phase == 0.0


def test_icon_visual_reactive_falls_back_to_base_brightness_when_perkey_brightness_read_fails() -> None:
    from keyrgb.tray.ui import icon

    class _Cfg:
        effect = "reactive_ripple"
        brightness = 10
        color = (10, 20, 30)
        reactive_color = (200, 100, 50)
        reactive_use_manual_color = False
        per_key_colors: ClassVar[dict] = {(0, 0): (255, 0, 0)}

        @property
        def perkey_brightness(self):
            raise RuntimeError("broken per-key brightness")

    visual = icon.icon_visual(config=_Cfg(), is_off=False, now=0.0)

    assert visual.mode == "rainbow"
    assert visual.scale == icon._animated_icon_scale_from_brightness(10)


def test_icon_visual_perkey_non_uniform_builds_full_grid_once(monkeypatch) -> None:
    from keyrgb.tray.ui import icon

    calls = {"count": 0}

    def fake_build_full_color_grid(*, base_color, per_key_colors, num_rows, num_cols):
        calls["count"] += 1
        full = {(r, c): tuple(base_color) for r in range(num_rows) for c in range(num_cols)}
        for key, value in per_key_colors.items():
            full[key] = value
        return full

    monkeypatch.setattr(icon, "build_full_color_grid", fake_build_full_color_grid)

    cfg = SimpleNamespace(
        effect="perkey",
        brightness=20,
        perkey_brightness=20,
        color=(255, 255, 255),
        per_key_colors={(0, 0): (255, 0, 0)},
    )

    visual = icon.icon_visual(config=cfg, is_off=False, now=0.0)

    assert visual.mode == "mosaic"
    assert calls["count"] == 1


def test_icon_visual_perkey_falls_back_to_base_brightness_when_perkey_brightness_read_fails() -> None:
    from keyrgb.tray.ui import icon

    class _Cfg:
        effect = "perkey"
        brightness = 10
        color = (255, 255, 255)
        per_key_colors: ClassVar[dict] = {(0, 0): (255, 0, 0)}

        @property
        def perkey_brightness(self):
            raise RuntimeError("broken per-key brightness")

    visual = icon.icon_visual(config=_Cfg(), is_off=False, now=0.0)

    assert visual.mode == "mosaic"
    assert visual.scale == icon._icon_scale_from_brightness(10)


def test_icon_visual_perkey_uniform_override_skips_full_grid_build(monkeypatch) -> None:
    from keyrgb.tray.ui import icon

    calls = {"count": 0}

    def fake_build_full_color_grid(*, base_color, per_key_colors, num_rows, num_cols):
        calls["count"] += 1
        return {(r, c): tuple(base_color) for r in range(num_rows) for c in range(num_cols)}

    monkeypatch.setattr(icon, "build_full_color_grid", fake_build_full_color_grid)

    cfg = SimpleNamespace(
        effect="perkey",
        brightness=20,
        perkey_brightness=20,
        color=(255, 255, 255),
        per_key_colors={(0, 0): (255, 255, 255)},
    )

    visual = icon.icon_visual(config=cfg, is_off=False, now=0.0)

    assert visual.mode == "solid"
    assert calls["count"] == 0
