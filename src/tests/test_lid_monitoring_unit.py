from __future__ import annotations

import builtins
import io
from unittest.mock import MagicMock

import pytest

from src.core.monitoring import lid_monitoring


class _ImmediateThread:
    def __init__(self, *, target, daemon: bool):
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        self._target()


def test_parse_lid_state_handles_open_closed_and_unknown() -> None:
    assert lid_monitoring._parse_lid_state("state: open") == "open"
    assert lid_monitoring._parse_lid_state("closed") == "closed"
    assert lid_monitoring._parse_lid_state("STATE: Closed\n") == "closed"
    assert lid_monitoring._parse_lid_state("something else") is None
    assert lid_monitoring._parse_lid_state("") is None
    assert lid_monitoring._parse_lid_state(None) is None


def test_start_sysfs_lid_monitoring_warns_when_no_lid_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lid_monitoring.glob, "glob", lambda _: [])

    # The implementation always starts the thread; the thread should exit
    # immediately after noticing there are no lid state files.
    monkeypatch.setattr(
        lid_monitoring.threading,
        "Thread",
        lambda *, target, daemon: _ImmediateThread(target=target, daemon=daemon),
    )

    logger = MagicMock()
    lid_monitoring.start_sysfs_lid_monitoring(
        is_running=lambda: True,
        on_lid_close=MagicMock(),
        on_lid_open=MagicMock(),
        logger=logger,
    )

    logger.warning.assert_called_once()


def test_start_sysfs_lid_monitoring_emits_callbacks_on_state_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lid_monitoring.glob, "glob", lambda _: ["/fake/lid/state"])
    monkeypatch.setattr(lid_monitoring.threading, "Thread", lambda *, target, daemon: _ImmediateThread(target=target, daemon=daemon))
    monkeypatch.setattr(lid_monitoring.time, "sleep", lambda _: None)

    states = [
        "state: open\n",
        "state: open\n",  # no change
        "state: closed\n",
        "state: closed\n",  # no change
        "nonsense\n",  # ignored
    ]
    i = {"idx": 0}

    def _open(_path, *args, **kwargs):
        # Each loop opens the file again.
        idx = min(i["idx"], len(states) - 1)
        i["idx"] += 1
        return io.StringIO(states[idx])

    monkeypatch.setattr(builtins, "open", _open)

    # Run exactly len(states) iterations.
    remaining = {"n": len(states)}

    def is_running() -> bool:
        remaining["n"] -= 1
        return remaining["n"] >= 0

    on_open = MagicMock()
    on_close = MagicMock()
    logger = MagicMock()

    lid_monitoring.start_sysfs_lid_monitoring(
        is_running=is_running,
        on_lid_close=on_close,
        on_lid_open=on_open,
        logger=logger,
    )

    on_open.assert_called_once()
    on_close.assert_called_once()


def test_poll_lid_state_paths_picks_first_readable_path_and_emits_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lid_monitoring.time, "sleep", lambda _: None)

    chosen_path = "/proc/acpi/button/lid/LID/state"

    reads = [
        "open\n",  # probe (find readable path)
        "open\n",  # first loop iteration
        "closed\n",  # second loop iteration
    ]
    calls = {"n": 0}

    def _open(path, *args, **kwargs):
        if path != chosen_path:
            raise FileNotFoundError(path)
        idx = min(calls["n"], len(reads) - 1)
        calls["n"] += 1
        return io.StringIO(reads[idx])

    monkeypatch.setattr(builtins, "open", _open)

    remaining = {"n": 2}

    def is_running() -> bool:
        remaining["n"] -= 1
        return remaining["n"] >= 0

    on_open = MagicMock()
    on_close = MagicMock()

    lid_monitoring.poll_lid_state_paths(
        is_running=is_running,
        on_lid_close=on_close,
        on_lid_open=on_open,
        logger=MagicMock(),
    )

    on_open.assert_called_once()
    on_close.assert_called_once()
