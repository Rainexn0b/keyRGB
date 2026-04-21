from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("255,0,0", None),
        (b"255,0,0", None),
        ((1, 2), None),
        (123, None),
        ((1, 2, 3), (1, 2, 3)),
    ],
)
def test_normalized_rgb_or_none_branches(value: object, expected: tuple[int, int, int] | None) -> None:
    from src.tray.ui.icon import _color

    assert _color._normalized_rgb_or_none(value) == expected


def test_normalized_color_values_filters_invalid_entries() -> None:
    from src.tray.ui.icon import _color

    raw_colors = [(1, 2, 3), (1, 2), "255,0,0", 123, (7, 8, 9)]
    assert _color._normalized_color_values(raw_colors) == ((1, 2, 3), (7, 8, 9))


def test_config_value_recovers_from_property_runtime_error() -> None:
    from src.tray.ui.icon import _color

    class _Cfg:
        @property
        def unstable(self):
            raise RuntimeError("transient")

    assert _color._config_value(_Cfg(), "unstable", 42) == 42


def test_weighted_hsv_mean_fallback_empty_iterable_uses_default() -> None:
    from src.tray.ui.icon import _color

    assert _color._weighted_hsv_mean(()) == (255, 0, 128)


def test_weighted_hsv_mean_fallback_total_too_low_uses_arithmetic_mean() -> None:
    from src.tray.ui.icon import _color

    # Black values keep v=0, so weighted total remains 0 and arithmetic fallback is used.
    assert _color._weighted_hsv_mean(((0, 0, 0), (0, 0, 0))) == (0, 0, 0)


def test_weighted_hsv_mean_fallback_zero_vector_uses_arithmetic_mean(monkeypatch) -> None:
    from src.tray.ui.icon import _color

    monkeypatch.setattr(_color.math, "cos", lambda _ang: 0.0)
    monkeypatch.setattr(_color.math, "sin", lambda _ang: 0.0)

    # total > 0 but x and y are forced to 0, so arithmetic fallback branch is used.
    assert _color._weighted_hsv_mean(((255, 0, 0), (0, 255, 0))) == (128, 128, 0)


def test_representative_perkey_color_fallback_when_grid_build_fails(monkeypatch) -> None:
    from src.tray.ui.icon import _color

    def _raise_grid_error(**_kwargs):
        raise ValueError("bad mapping")

    monkeypatch.setattr(_color, "build_full_color_grid", _raise_grid_error)
    cfg = SimpleNamespace(
        color=(0, 0, 0),
        per_key_colors={(0, 0): (255, 0, 0), (0, 1): (0, 255, 0)},
    )

    expected = _color._weighted_hsv_mean(((255, 0, 0), (0, 255, 0)))
    assert _color._representative_perkey_color(cfg) == expected


def test_representative_perkey_color_uses_full_grid_when_available(monkeypatch) -> None:
    from src.tray.ui.icon import _color

    def _fake_build_full_color_grid(**_kwargs):
        return {(0, 0): (10, 20, 30), (0, 1): (200, 100, 50)}

    monkeypatch.setattr(_color, "build_full_color_grid", _fake_build_full_color_grid)
    cfg = SimpleNamespace(
        color=(1, 2, 3),
        per_key_colors={(0, 0): (255, 0, 0)},
    )

    expected = _color._weighted_hsv_mean(((10, 20, 30), (200, 100, 50)))
    assert _color._representative_perkey_color(cfg) == expected


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


def test_representative_color_off_state_returns_off_color() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(effect="none", brightness=50, color=(255, 0, 0))
    assert representative_color(config=cfg, is_off=True, now=0.0) == (64, 64, 64)


@pytest.mark.parametrize(
    "effect",
    ["rainbow_wave", "rainbow_swirl", "color_cycle", "spectrum_cycle"],
)
def test_representative_color_multicolor_effects(effect: str) -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(effect=effect, brightness=25, speed=5, color=(1, 2, 3))
    out = representative_color(config=cfg, is_off=False, now=123.0)
    assert isinstance(out, tuple)
    assert len(out) == 3
    assert all(0 <= v <= 255 for v in out)


def test_representative_color_hardware_effect_branch() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(effect="rainbow", brightness=20, speed=5, color=(1, 2, 3))
    out = representative_color(config=cfg, is_off=False, now=15.0)
    assert isinstance(out, tuple)
    assert len(out) == 3
    assert all(0 <= v <= 255 for v in out)


def test_representative_color_perkey_branch_prefers_perkey_brightness_and_color(monkeypatch) -> None:
    from src.tray.ui.icon import _color

    monkeypatch.setattr(_color, "_representative_perkey_color", lambda _cfg: (100, 80, 60))
    cfg = SimpleNamespace(effect="perkey", brightness=1, perkey_brightness=20, color=(1, 2, 3))

    # perkey_brightness=20 -> icon_brightness=50 -> full scale
    assert _color.representative_color(config=cfg, is_off=False, now=0.0) == (100, 80, 60)


def test_representative_color_non_reactive_default_path_uses_config_color() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(effect="static", brightness=10, color=(20, 40, 60))
    assert representative_color(config=cfg, is_off=False, now=0.0) == (12, 24, 36)


def test_representative_color_reactive_manual_false_uses_saved_perkey_fallback(monkeypatch) -> None:
    from src.tray.ui.icon import _color

    monkeypatch.setattr(_color, "_representative_saved_perkey_color", lambda _cfg: (5, 10, 15))
    cfg = SimpleNamespace(
        effect="reactive_fade",
        brightness=5,
        perkey_brightness=10,
        color=(200, 100, 50),
        reactive_use_manual_color=False,
    )
    # perkey_brightness=10 -> icon scale 0.6
    assert _color.representative_color(config=cfg, is_off=False, now=0.0) == (3, 6, 9)


def test_representative_color_reactive_manual_true_uses_manual_reactive_color() -> None:
    from src.tray.ui.icon import representative_color

    cfg = SimpleNamespace(
        effect="reactive_fade",
        brightness=10,
        color=(10, 20, 30),
        reactive_color=(200, 100, 50),
        reactive_use_manual_color=True,
    )
    assert representative_color(config=cfg, is_off=False, now=0.0) == (120, 60, 30)


def test_representative_color_brightness_scaling_clamps_low_and_high() -> None:
    from src.tray.ui.icon import representative_color

    low = SimpleNamespace(effect="none", brightness=-10, color=(100, 50, 0))
    high = SimpleNamespace(effect="none", brightness=999, color=(100, 50, 0))

    assert representative_color(config=low, is_off=False, now=0.0) == (25, 12, 0)
    assert representative_color(config=high, is_off=False, now=0.0) == (100, 50, 0)


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
