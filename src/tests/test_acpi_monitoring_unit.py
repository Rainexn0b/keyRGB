from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.monitoring import acpi_monitoring


class _FakeStdout:
    def __init__(self, lines: list[str]):
        self._lines = list(lines)

    def readline(self) -> str:
        if not self._lines:
            return ""
        return self._lines.pop(0)


class _FakeProcess:
    def __init__(self, lines: list[str]):
        self.stdout = _FakeStdout(lines)


def test_parse_acpi_lid_event_recognizes_open_close() -> None:
    assert acpi_monitoring._parse_acpi_lid_event("button/lid LID close") == "closed"
    assert acpi_monitoring._parse_acpi_lid_event("button/lid LID open") == "open"
    assert acpi_monitoring._parse_acpi_lid_event("something else") is None
    assert acpi_monitoring._parse_acpi_lid_event("") is None


def test_monitor_acpi_events_emits_callbacks_for_lid_events(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProcess(
        [
            "ac_adapter ACPI0003:00 00000080 00000001\n",
            "button/lid LID close\n",
            "button/lid LID open\n",
            "button/lid LID close\n",
        ]
    )

    monkeypatch.setattr(acpi_monitoring.subprocess, "Popen", lambda *a, **k: fake)

    remaining = {"n": 10}

    def is_running() -> bool:
        remaining["n"] -= 1
        return remaining["n"] >= 0

    on_close = MagicMock()
    on_open = MagicMock()

    acpi_monitoring.monitor_acpi_events(
        is_running=is_running,
        on_lid_close=on_close,
        on_lid_open=on_open,
        logger=MagicMock(),
    )

    assert on_close.call_count == 2
    assert on_open.call_count == 1


def test_monitor_acpi_events_falls_back_when_acpi_listen_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError("acpi_listen")

    monkeypatch.setattr(acpi_monitoring.subprocess, "Popen", _raise)

    poll = MagicMock()
    monkeypatch.setattr(acpi_monitoring, "poll_lid_state_paths", poll)

    on_close = MagicMock()
    on_open = MagicMock()

    acpi_monitoring.monitor_acpi_events(
        is_running=lambda: True,
        on_lid_close=on_close,
        on_lid_open=on_open,
        logger=MagicMock(),
    )

    poll.assert_called_once()
    # Ensure callbacks are wired through to the fallback.
    _, kwargs = poll.call_args
    assert kwargs["on_lid_close"] is on_close
    assert kwargs["on_lid_open"] is on_open
