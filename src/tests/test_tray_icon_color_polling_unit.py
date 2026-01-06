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
    assert sig[1] == ""
    assert sig[2] == 4
    assert sig[3] == 0
    assert sig[4] == (1, 2, 3)


def test_compute_icon_sig_handles_missing_config():
    tray = SimpleNamespace(is_off=False)
    assert icp._compute_icon_sig(tray) == (False, "", 0, 0, (0, 0, 0))


def test_should_update_icon_updates_on_change_for_non_dynamic_effect():
    last_sig = (False, "perkey", 1, 10, (0, 0, 0))
    sig = (False, "perkey", 2, 10, (0, 0, 0))

    assert icp._should_update_icon(sig, last_sig) is True
    assert icp._should_update_icon(last_sig, last_sig) is False


def test_should_update_icon_always_updates_for_dynamic_effect_even_if_unchanged():
    sig = (False, "rainbow", 1, 10, (0, 0, 0))
    assert icp._should_update_icon(sig, sig) is True


def test_normalize_color_falls_back_on_invalid():
    assert icp._normalize_color(None) == (0, 0, 0)
    assert icp._normalize_color((1, 2, 3)) == (1, 2, 3)
    assert icp._normalize_color([1, 2, 3]) == (1, 2, 3)
    assert icp._normalize_color([1, 2]) == (0, 0, 0)
    assert icp._normalize_color("not-a-seq") == (0, 0, 0)
