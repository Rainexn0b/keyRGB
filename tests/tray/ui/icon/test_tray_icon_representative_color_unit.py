from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_representative_color_boosts_visibility_at_low_brightness() -> None:
    from src.tray.ui.icon import representative_color

    # At low brightness, the icon should be brighter than a 1:1 mapping.
    # With 1:3 scaling, brightness=5 -> icon_brightness=15 -> scale=0.3.
    cfg = SimpleNamespace(effect="none", brightness=5, color=(255, 0, 0))
    r, g, b = representative_color(config=cfg, is_off=False, now=0.0)

    assert (r, g, b) == (76, 0, 0)


def test_representative_color_clamps_min_visibility() -> None:
    from src.tray.ui.icon import representative_color

    # Even extremely low brightness should keep a minimum icon visibility.
    # brightness=1 -> icon_brightness=3 -> scale=0.06 but clamped to 0.25.
    cfg = SimpleNamespace(effect="none", brightness=1, color=(200, 100, 0))
    r, g, b = representative_color(config=cfg, is_off=False, now=0.0)

    assert (r, g, b) == (50, 25, 0)


def test_representative_color_clamps_max() -> None:
    from src.tray.ui.icon import representative_color

    # High brightness should not exceed full intensity.
    cfg = SimpleNamespace(effect="none", brightness=50, color=(10, 20, 30))
    assert representative_color(config=cfg, is_off=False, now=0.0) == (10, 20, 30)


def test_representative_color_reactive_typing_never_black_when_on() -> None:
    from src.tray.ui.icon import representative_color

    # Default dim profile can have a black base color, but the tray icon should
    # still remain visible.
    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=5,
        perkey_brightness=5,
        color=(0, 0, 0),
        reactive_color=None,
    )
    assert representative_color(config=cfg, is_off=False, now=0.0) != (0, 0, 0)


def test_representative_color_reactive_typing_uses_base_brightness_not_reactive_brightness() -> None:
    from src.tray.ui.icon import representative_color

    # The tray icon should reflect the keyboard/profile brightness (policies)
    # and not the reactive pulse intensity.
    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=5,
        reactive_brightness=50,
        color=(255, 0, 0),
        reactive_color=(255, 0, 0),
    )
    assert representative_color(config=cfg, is_off=False, now=0.0) == (76, 0, 0)


def test_representative_color_reactive_manual_color_respects_toggle() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=10,
        color=(10, 20, 30),
        reactive_color=(200, 100, 50),
        reactive_use_manual_color=False,
    )

    # Manual override disabled -> follow base color, not the stored reactive color.
    assert representative_color(config=cfg, is_off=False, now=0.0) == (6, 12, 18)

    cfg.reactive_use_manual_color = True
    assert representative_color(config=cfg, is_off=False, now=0.0) == (120, 60, 30)


def test_representative_color_reactive_uses_uniform_perkey_profile_color_when_manual_disabled() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(
        effect="reactive_ripple",
        brightness=10,
        perkey_brightness=10,
        color=(255, 0, 0),
        reactive_color=(255, 0, 0),
        reactive_use_manual_color=False,
        per_key_colors={(0, 0): (255, 255, 255)},
    )

    assert representative_color(config=cfg, is_off=False, now=0.0) == (153, 153, 153)


def test_representative_color_perkey_falls_back_to_base_color_for_malformed_entries() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(
        effect="perkey",
        brightness=10,
        perkey_brightness=10,
        color=(10, 20, 30),
        per_key_colors={(0, 0): (255, 0)},
    )

    assert representative_color(config=cfg, is_off=False, now=0.0) == (6, 12, 18)


def test_representative_color_handles_config_property_exceptions_non_fatally() -> None:
    from src.tray.ui.icon import representative_color

    class _Cfg:
        effect = "reactive_fade"
        brightness = 10
        perkey_brightness = 10
        reactive_use_manual_color = False

        @property
        def per_key_colors(self):
            raise RuntimeError("boom")

        @property
        def color(self):
            raise RuntimeError("boom")

    assert representative_color(config=_Cfg(), is_off=False, now=0.0) == (153, 0, 76)


def test_representative_color_propagates_unexpected_config_property_errors() -> None:
    from src.tray.ui.icon import representative_color

    class _Cfg:
        effect = "reactive_fade"
        brightness = 10
        perkey_brightness = 10
        reactive_use_manual_color = False

        @property
        def per_key_colors(self):
            raise AssertionError("unexpected config bug")

    with pytest.raises(AssertionError, match="unexpected config bug"):
        representative_color(config=_Cfg(), is_off=False, now=0.0)


def test_icon_visual_reactive_uses_base_mosaic_when_manual_color_disabled() -> None:
    from src.tray.ui.icon import icon_visual

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
    from src.tray.ui.icon import icon_visual

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
    from src.tray.ui.icon import icon_visual

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
    from src.tray.ui import icon

    class _Cfg:
        effect = "reactive_ripple"
        brightness = 10
        color = (10, 20, 30)
        reactive_color = (200, 100, 50)
        reactive_use_manual_color = False
        per_key_colors = {(0, 0): (255, 0, 0)}

        @property
        def perkey_brightness(self):
            raise RuntimeError("broken per-key brightness")

    visual = icon.icon_visual(config=_Cfg(), is_off=False, now=0.0)

    assert visual.mode == "rainbow"
    assert visual.scale == icon._animated_icon_scale_from_brightness(10)


def test_icon_visual_perkey_non_uniform_builds_full_grid_once(monkeypatch) -> None:
    from src.tray.ui import icon

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
    from src.tray.ui import icon

    class _Cfg:
        effect = "perkey"
        brightness = 10
        color = (255, 255, 255)
        per_key_colors = {(0, 0): (255, 0, 0)}

        @property
        def perkey_brightness(self):
            raise RuntimeError("broken per-key brightness")

    visual = icon.icon_visual(config=_Cfg(), is_off=False, now=0.0)

    assert visual.mode == "mosaic"
    assert visual.scale == icon._icon_scale_from_brightness(10)


def test_icon_visual_perkey_uniform_override_skips_full_grid_build(monkeypatch) -> None:
    from src.tray.ui import icon

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
