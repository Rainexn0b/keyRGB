from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from keyrgb.core.power.monitoring.login1_monitoring import iter_prepare_for_sleep_events


class _FakeStdout:
    def __init__(self, lines: list[str], *, on_read=None):
        self._lines = list(lines)
        self._on_read = on_read

    def readline(self) -> str:
        if self._on_read is not None:
            self._on_read()
        if not self._lines:
            return ""
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self, lines: list[str], *, on_read=None):
        self.stdout = _FakeStdout(lines, on_read=on_read)
        self.stderr = _FakeStdout([])


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


def test_monitor_prepare_for_sleep_calls_on_started_and_emits_callbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.power.monitoring import login1_monitoring

    fake = _FakeProcess(
        [
            "noise\n",
            "signal sender=:1.1 -> PrepareForSleep\n",
            "   boolean true\n",
            "signal sender=:1.1 -> PrepareForSleep\n",
            "   boolean false\n",
        ]
    )

    popen_calls: list[list[str]] = []

    def _popen(cmd, **kwargs):
        popen_calls.append(list(cmd))
        return fake

    monkeypatch.setattr(login1_monitoring.subprocess, "Popen", _popen)

    on_started = MagicMock()
    on_suspend = MagicMock()
    on_resume = MagicMock()

    remaining = {"n": 20}

    def is_running() -> bool:
        remaining["n"] -= 1
        return remaining["n"] >= 0

    login1_monitoring.monitor_prepare_for_sleep(
        is_running=is_running,
        on_suspend=on_suspend,
        on_resume=on_resume,
        on_started=on_started,
    )

    on_started.assert_called_once()
    on_suspend.assert_called_once()
    on_resume.assert_called_once()
    assert popen_calls and popen_calls[0][0] == "dbus-monitor"


def test_monitor_prepare_for_sleep_ignores_unexpected_boolean_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.power.monitoring import login1_monitoring

    fake = _FakeProcess(
        [
            "signal -> PrepareForSleep\n",
            "   boolean maybe\n",
            "signal -> PrepareForSleep\n",
            "   boolean true\n",
        ]
    )

    monkeypatch.setattr(login1_monitoring.subprocess, "Popen", lambda *a, **k: fake)

    on_suspend = MagicMock()
    on_resume = MagicMock()

    login1_monitoring.monitor_prepare_for_sleep(
        is_running=lambda: True,
        on_suspend=on_suspend,
        on_resume=on_resume,
        on_started=None,
    )

    on_suspend.assert_called_once()
    on_resume.assert_not_called()


def test_monitor_prepare_for_sleep_does_not_callback_after_shutdown_during_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.power.monitoring import login1_monitoring

    running = {"value": True}
    fake = _FakeProcess(
        ["signal -> PrepareForSleep\n", "   boolean true\n"],
        on_read=lambda: running.__setitem__("value", False),
    )
    monkeypatch.setattr(login1_monitoring.subprocess, "Popen", lambda *a, **k: fake)
    on_suspend = MagicMock()
    on_process_started = MagicMock()
    on_process_stopped = MagicMock()

    login1_monitoring.monitor_prepare_for_sleep(
        is_running=lambda: running["value"],
        on_suspend=on_suspend,
        on_resume=MagicMock(),
        on_process_started=on_process_started,
        on_process_stopped=on_process_stopped,
    )

    on_suspend.assert_not_called()
    on_process_started.assert_called_once_with(fake)
    on_process_stopped.assert_called_once_with(fake)
