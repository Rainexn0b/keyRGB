from __future__ import annotations

from types import SimpleNamespace

from src.tray.pollers import icon_color_polling as icp


def test_compute_icon_sig_normalizes_fields():
    tray = SimpleNamespace(
        is_off=1,
        config=SimpleNamespace(effect=None, speed="4", brightness=None, color=["1", 2, 3]),
    )
    sig = icp._compute_icon_sig(tray)

    assert sig[0] is True
    assert sig[1] == "none"
    assert sig[2] == 4
    assert sig[3] == 0
    assert sig[4] == (1, 2, 3)
    assert sig[5] is False


def test_compute_icon_sig_handles_missing_config():
    tray = SimpleNamespace(is_off=False)
    assert icp._compute_icon_sig(tray) == (False, "none", 0, 0, (0, 0, 0), False)


def test_should_update_icon_updates_on_change_for_non_dynamic_effect():
    last_sig = (False, "perkey", 1, 10, (0, 0, 0), False)
    sig = (False, "perkey", 2, 10, (0, 0, 0), False)

    assert icp._should_update_icon(sig, last_sig) is True
    assert icp._should_update_icon(last_sig, last_sig) is False


def test_should_update_icon_always_updates_for_dynamic_effect_even_if_unchanged():
    sig = (False, "rainbow", 1, 10, (0, 0, 0), True)
    assert icp._should_update_icon(sig, sig) is True


def test_compute_icon_sig_marks_reactive_ripple_as_animated_without_manual_color():
    tray = SimpleNamespace(
        is_off=False,
        config=SimpleNamespace(
            effect="reactive_ripple",
            speed=5,
            brightness=25,
            color=(1, 2, 3),
            reactive_use_manual_color=False,
        ),
    )

    sig = icp._compute_icon_sig(tray)
    assert sig[5] is True


def test_normalize_color_falls_back_on_invalid():
    assert icp._normalize_color(None) == (0, 0, 0)
    assert icp._normalize_color((1, 2, 3)) == (1, 2, 3)
    assert icp._normalize_color([1, 2, 3]) == (1, 2, 3)
    assert icp._normalize_color([1, 2]) == (0, 0, 0)
    assert icp._normalize_color("not-a-seq") == (0, 0, 0)
