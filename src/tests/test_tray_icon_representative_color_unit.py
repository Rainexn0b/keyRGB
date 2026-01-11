from __future__ import annotations

from types import SimpleNamespace


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
