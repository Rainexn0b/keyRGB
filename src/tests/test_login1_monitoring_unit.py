from __future__ import annotations

from src.core.login1_monitoring import iter_prepare_for_sleep_events


def test_iter_prepare_for_sleep_events_emits_suspend_and_resume() -> None:
    lines = [
        "some unrelated line\n",
        "signal sender=:1.1 -> PrepareForSleep\n",
        "   boolean true\n",
        "another unrelated line\n",
        "signal sender=:1.1 -> PrepareForSleep\n",
        "   boolean false\n",
    ]

    assert list(iter_prepare_for_sleep_events(lines)) == [True, False]


def test_iter_prepare_for_sleep_events_ignores_missing_value_line() -> None:
    lines = [
        "signal -> PrepareForSleep\n",
    ]

    assert list(iter_prepare_for_sleep_events(lines)) == []
