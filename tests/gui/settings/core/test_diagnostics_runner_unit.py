from __future__ import annotations

import json
import logging
import sys
from types import ModuleType

import pytest

import src.gui.settings.diagnostics_runner as runner


def test_expected_holder_pids_uses_tray_pid_env(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_TRAY_PID", "4242")
    monkeypatch.setattr(runner.os, "getppid", lambda: 9999)

    assert runner._expected_holder_pids() == {4242}


def test_expected_holder_pids_falls_back_to_keyrgb_parent(monkeypatch) -> None:
    monkeypatch.delenv("KEYRGB_TRAY_PID", raising=False)
    monkeypatch.setattr(runner.os, "getppid", lambda: 3141)

    class FakePath:
        def __init__(self, value: str):
            self.value = value

        def exists(self) -> bool:
            return self.value == "/proc/3141/comm"

        def read_text(self, *, encoding: str, errors: str) -> str:
            assert encoding == "utf-8"
            assert errors == "ignore"
            return "keyrgb\n"

    monkeypatch.setattr(runner, "Path", FakePath)

    assert runner._expected_holder_pids() == {3141}


def test_expected_holder_pids_ignores_invalid_env_and_non_keyrgb_parent(monkeypatch) -> None:
    monkeypatch.setenv("KEYRGB_TRAY_PID", "not-a-pid")
    monkeypatch.setattr(runner.os, "getppid", lambda: 2718)

    class FakePath:
        def __init__(self, value: str):
            self.value = value

        def exists(self) -> bool:
            return self.value == "/proc/2718/comm"

        def read_text(self, *, encoding: str, errors: str) -> str:
            assert encoding == "utf-8"
            assert errors == "ignore"
            return "python\n"

    monkeypatch.setattr(runner, "Path", FakePath)

    assert runner._expected_holder_pids() == set()


def test_expected_holder_pids_returns_empty_when_parent_probe_raises(monkeypatch) -> None:
    monkeypatch.delenv("KEYRGB_TRAY_PID", raising=False)
    monkeypatch.setattr(runner.os, "getppid", lambda: 2718)
    monkeypatch.setattr(runner, "Path", lambda _value: (_ for _ in ()).throw(OSError("boom")))

    assert runner._expected_holder_pids() == set()


def test_device_busy_warnings_filters_expected_holder_pids() -> None:
    payload = {
        "usb_devices": [
            {
                "devnode": "/dev/hidraw0",
                "devnode_open_by_others": [
                    {"pid": 101, "comm": "keyrgb", "exe": "/usr/bin/keyrgb"},
                    {"pid": "202", "comm": "openrgb", "exe": "/usr/bin/openrgb"},
                ],
            }
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids={101})

    assert warnings == [
        "Device busy: /dev/hidraw0 is open by other process(es): pid=202 comm=openrgb exe=/usr/bin/openrgb"
    ]


def test_device_busy_warnings_uses_generic_message_without_holder_details() -> None:
    payload = {
        "usb_devices": [
            {
                "sysfs_path": "/sys/devices/platform/mock0",
                "devnode_open_by_others": [{}, "skip-me"],
            }
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids=set())

    assert warnings == ["Device busy: /sys/devices/platform/mock0 is open by other process(es)"]


def test_device_busy_warnings_returns_empty_when_usb_devices_is_not_a_list() -> None:
    warnings = runner._device_busy_warnings({"usb_devices": "bad-shape"}, expected_holder_pids=set())

    assert warnings == []


def test_device_busy_warnings_omits_warning_when_only_expected_holders_exist() -> None:
    payload = {
        "usb_devices": [
            {
                "devnode": "/dev/hidraw0",
                "devnode_open_by_others": [
                    {"pid": 101, "comm": "keyrgb", "exe": "/usr/bin/keyrgb"},
                ],
            }
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids={101})

    assert warnings == []


def test_device_busy_warnings_uses_unknown_devnode_when_paths_are_missing() -> None:
    payload = {
        "usb_devices": [
            {
                "devnode_open_by_others": [
                    {"comm": "openrgb"},
                ],
            }
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids=set())

    assert warnings == ["Device busy: (unknown) is open by other process(es): comm=openrgb"]


def test_device_busy_warnings_keeps_unparseable_holder_pid() -> None:
    payload = {
        "usb_devices": [
            {
                "devnode": "/dev/hidraw0",
                "devnode_open_by_others": [
                    {"pid": "not-a-pid", "comm": "openrgb"},
                ],
            }
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids={101})

    assert warnings == ["Device busy: /dev/hidraw0 is open by other process(es): pid=not-a-pid comm=openrgb"]


class _BrokenString:
    def __str__(self) -> str:
        raise RuntimeError("boom")


def test_device_busy_warnings_returns_partial_results_on_malformed_holder_data(caplog) -> None:
    payload = {
        "usb_devices": [
            {
                "devnode": "/dev/hidraw0",
                "devnode_open_by_others": [
                    {"pid": 202, "comm": "openrgb"},
                ],
            },
            {
                "devnode": "/dev/hidraw1",
                "devnode_open_by_others": [
                    {"comm": _BrokenString()},
                ],
            },
        ]
    }

    warnings = runner._device_busy_warnings(payload, expected_holder_pids=set())

    assert warnings == ["Device busy: /dev/hidraw0 is open by other process(es): pid=202 comm=openrgb"]
    records = [
        record for record in caplog.records if record.getMessage() == "Failed to build device-busy diagnostics warnings"
    ]
    assert len(records) == 1
    assert records[0].exc_info is not None


def test_device_busy_warnings_propagates_unexpected_programming_errors() -> None:
    class _BrokenDevice(dict):
        def get(self, key, default=None):
            if key == "devnode_open_by_others":
                raise AssertionError("boom")
            return super().get(key, default)

    payload = {"usb_devices": [_BrokenDevice(devnode="/dev/hidraw0")]}

    with pytest.raises(AssertionError):
        runner._device_busy_warnings(payload, expected_holder_pids=set())


def test_collect_diagnostics_text_serializes_payload_and_injects_warnings(monkeypatch) -> None:
    calls: dict[str, bool] = {}

    class FakeDiagnostics:
        def to_dict(self) -> dict[str, object]:
            return {
                "usb_devices": [
                    {
                        "devnode": "/dev/hidraw7",
                        "devnode_open_by_others": [{"pid": 77, "comm": "other-app", "exe": "/usr/bin/other-app"}],
                    }
                ],
                "status": "ok",
            }

    def fake_collect_diagnostics(*, include_usb: bool) -> FakeDiagnostics:
        calls["include_usb"] = include_usb
        return FakeDiagnostics()

    fake_module = ModuleType("src.core.diagnostics")
    fake_module.collect_diagnostics = fake_collect_diagnostics  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "src.core.diagnostics", fake_module)
    monkeypatch.setattr(runner, "_expected_holder_pids", lambda: set())

    payload = json.loads(runner.collect_diagnostics_text(include_usb=False))

    assert calls == {"include_usb": False}
    assert payload["status"] == "ok"
    assert payload["warnings"] == [
        "Device busy: /dev/hidraw7 is open by other process(es): pid=77 comm=other-app exe=/usr/bin/other-app"
    ]


def test_collect_diagnostics_text_omits_warnings_when_busy_holders_are_expected(monkeypatch) -> None:
    class FakeDiagnostics:
        def to_dict(self) -> dict[str, object]:
            return {
                "usb_devices": [
                    {
                        "devnode": "/dev/hidraw7",
                        "devnode_open_by_others": [{"pid": 77, "comm": "keyrgb", "exe": "/usr/bin/keyrgb"}],
                    }
                ],
                "status": "ok",
            }

    def fake_collect_diagnostics(*, include_usb: bool) -> FakeDiagnostics:
        assert include_usb is True
        return FakeDiagnostics()

    fake_module = ModuleType("src.core.diagnostics")
    fake_module.collect_diagnostics = fake_collect_diagnostics  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "src.core.diagnostics", fake_module)
    monkeypatch.setattr(runner, "_expected_holder_pids", lambda: {77})

    payload = json.loads(runner.collect_diagnostics_text())

    assert payload == {
        "status": "ok",
        "usb_devices": [
            {
                "devnode": "/dev/hidraw7",
                "devnode_open_by_others": [{"pid": 77, "comm": "keyrgb", "exe": "/usr/bin/keyrgb"}],
            }
        ],
    }


def test_collect_diagnostics_text_sorts_json_keys(monkeypatch) -> None:
    class FakeDiagnostics:
        def to_dict(self) -> dict[str, object]:
            return {
                "zeta": 1,
                "alpha": 2,
                "usb_devices": [],
            }

    fake_module = ModuleType("src.core.diagnostics")
    fake_module.collect_diagnostics = lambda *, include_usb: FakeDiagnostics()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "src.core.diagnostics", fake_module)
    monkeypatch.setattr(runner, "_expected_holder_pids", lambda: set())

    text = runner.collect_diagnostics_text()

    assert '"warnings"' not in text
    assert text.index('"alpha"') < text.index('"usb_devices"') < text.index('"zeta"')


def test_collect_diagnostics_text_preserves_sysfs_mouse_candidate_details(monkeypatch) -> None:
    class FakeDiagnostics:
        def to_dict(self) -> dict[str, object]:
            return {
                "backends": {
                    "selected": "sysfs-leds",
                    "sysfs_mouse_candidates": {
                        "candidates_count": 1,
                        "matched_count": 0,
                        "eligible_count": 0,
                        "top": [
                            {
                                "name": "steelseries::logo",
                                "matched": False,
                                "eligible": False,
                                "score": 0,
                                "reasons": ["no mouse/pointer evidence in LED name or device metadata"],
                            }
                        ],
                    },
                },
                "usb_devices": [],
            }

    fake_module = ModuleType("src.core.diagnostics")
    fake_module.collect_diagnostics = lambda *, include_usb: FakeDiagnostics()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "src.core.diagnostics", fake_module)
    monkeypatch.setattr(runner, "_expected_holder_pids", lambda: set())

    payload = json.loads(runner.collect_diagnostics_text())

    assert payload["backends"]["sysfs_mouse_candidates"]["candidates_count"] == 1
    assert payload["backends"]["sysfs_mouse_candidates"]["top"][0]["name"] == "steelseries::logo"
    assert payload["backends"]["sysfs_mouse_candidates"]["top"][0]["reasons"] == [
        "no mouse/pointer evidence in LED name or device metadata"
    ]
