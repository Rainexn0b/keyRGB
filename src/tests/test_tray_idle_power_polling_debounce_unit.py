from __future__ import annotations

from src.tray.pollers import idle_power_polling as ipp


def test_debounce_dimmed_requires_two_true_polls():
    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=True,
        screen_off_raw=False,
        dimmed_true_streak=0,
        dimmed_false_streak=0,
        screen_off_true_streak=0,
        debounce_polls=2,
    )
    assert dimmed is None
    assert screen_off is False
    assert (t, f, so) == (1, 0, 0)

    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=True,
        screen_off_raw=False,
        dimmed_true_streak=t,
        dimmed_false_streak=f,
        screen_off_true_streak=so,
        debounce_polls=2,
    )
    assert dimmed is True
    assert screen_off is False


def test_debounce_dimmed_requires_two_false_polls():
    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=False,
        screen_off_raw=False,
        dimmed_true_streak=0,
        dimmed_false_streak=0,
        screen_off_true_streak=0,
        debounce_polls=2,
    )
    assert dimmed is None

    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=False,
        screen_off_raw=False,
        dimmed_true_streak=t,
        dimmed_false_streak=f,
        screen_off_true_streak=so,
        debounce_polls=2,
    )
    assert dimmed is False


def test_debounce_dimmed_unknown_resets_streaks():
    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=True,
        screen_off_raw=False,
        dimmed_true_streak=0,
        dimmed_false_streak=0,
        screen_off_true_streak=0,
        debounce_polls=2,
    )
    assert (t, f) == (1, 0)

    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=None,
        screen_off_raw=False,
        dimmed_true_streak=t,
        dimmed_false_streak=f,
        screen_off_true_streak=so,
        debounce_polls=2,
    )
    assert dimmed is None
    assert (t, f) == (0, 0)


def test_debounce_screen_off_requires_two_true_polls():
    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=None,
        screen_off_raw=True,
        dimmed_true_streak=0,
        dimmed_false_streak=0,
        screen_off_true_streak=0,
        debounce_polls=2,
    )
    assert screen_off is False
    assert so == 1

    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=None,
        screen_off_raw=True,
        dimmed_true_streak=t,
        dimmed_false_streak=f,
        screen_off_true_streak=so,
        debounce_polls=2,
    )
    assert screen_off is True


def test_debounce_screen_off_false_resets_streak():
    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=None,
        screen_off_raw=True,
        dimmed_true_streak=0,
        dimmed_false_streak=0,
        screen_off_true_streak=1,
        debounce_polls=2,
    )
    assert so == 2

    dimmed, screen_off, t, f, so = ipp._debounce_dim_and_screen_off(
        dimmed_raw=None,
        screen_off_raw=False,
        dimmed_true_streak=t,
        dimmed_false_streak=f,
        screen_off_true_streak=so,
        debounce_polls=2,
    )
    assert screen_off is False
    assert so == 0
