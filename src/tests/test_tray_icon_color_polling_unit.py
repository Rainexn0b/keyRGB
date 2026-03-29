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


def test_compute_icon_sig_resolves_legacy_effect_against_backend():
    class _Backend:
        def effects(self):
            return {}

    tray = SimpleNamespace(
        is_off=False,
        backend=_Backend(),
        config=SimpleNamespace(effect="wave", speed="4", brightness=10, color=["1", 2, 3]),
    )

    sig = icp._compute_icon_sig(tray)
    assert sig == (False, "none", 4, 10, (1, 2, 3), False)


def test_compute_icon_sig_marks_normalized_software_rainbow_as_dynamic() -> None:
    class _Backend:
        def effects(self):
            return {}

    tray = SimpleNamespace(
        is_off=False,
        backend=_Backend(),
        config=SimpleNamespace(effect="rainbow", speed=4, brightness=10, color=(1, 2, 3)),
    )

    sig = icp._compute_icon_sig(tray)
    assert sig == (False, "rainbow_wave", 4, 10, (1, 2, 3), True)


def test_compute_icon_sig_marks_reactive_ripple_dynamic_only_without_manual_override() -> None:
    tray = SimpleNamespace(
        is_off=False,
        config=SimpleNamespace(
            effect="reactive_ripple",
            speed=4,
            brightness=10,
            color=(1, 2, 3),
            reactive_use_manual_color=False,
        ),
    )

    sig = icp._compute_icon_sig(tray)
    assert sig == (False, "reactive_ripple", 4, 10, (1, 2, 3), True)

    tray.config.reactive_use_manual_color = True
    sig = icp._compute_icon_sig(tray)
    assert sig == (False, "reactive_ripple", 4, 10, (1, 2, 3), False)


def test_should_update_icon_updates_on_change_for_non_dynamic_effect():
    last_sig = (False, "perkey", 1, 10, (0, 0, 0), False)
    sig = (False, "perkey", 2, 10, (0, 0, 0), False)

    assert icp._should_update_icon(sig, last_sig) is True
    assert icp._should_update_icon(last_sig, last_sig) is False


def test_should_update_icon_always_updates_for_animated_icon_state_even_if_unchanged():
    sig = (False, "rainbow_wave", 1, 10, (0, 0, 0), True)
    assert icp._should_update_icon(sig, sig) is True


def test_normalize_color_falls_back_on_invalid():
    assert icp._normalize_color(None) == (0, 0, 0)
    assert icp._normalize_color((1, 2, 3)) == (1, 2, 3)
    assert icp._normalize_color([1, 2, 3]) == (1, 2, 3)
    assert icp._normalize_color([1, 2]) == (0, 0, 0)
    assert icp._normalize_color("not-a-seq") == (0, 0, 0)
