from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path as RealPath

import pytest

from src.core import diagnostics as diagnostics_mod
from src.core.diagnostics.model import Diagnostics
from src.core.diagnostics.proc import proc_open_holders
import src.core.diagnostics.proc as proc_mod


def _sample_diagnostics() -> Diagnostics:
    return Diagnostics(
        dmi={"sys_vendor": "Tongfang"},
        leds=[],
        sysfs_leds=[],
        usb_ids=["048d:ce00"],
        env={"KEYRGB_DEBUG": "1"},
        virt={},
        system={"platform": "linux"},
        hints={},
        app={"version": "test"},
        power_supply={},
        backends={"selected": "ite8291r3", "probes": []},
        usb_devices=[],
        config={"backend": "auto"},
        process={"pid": 1234},
    )


def test_collect_diagnostics_filters_usb_targets_and_tolerates_power_mode_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_usb_targets: list[tuple[int, int]] = []

    monkeypatch.setattr(diagnostics_mod, "_dmi_snapshot", lambda: {"sys_vendor": "Tongfang"})
    monkeypatch.setattr(diagnostics_mod, "_sysfs_leds_snapshot", lambda: ([{"name": "all"}], [{"name": "kbd"}]))
    monkeypatch.setattr(diagnostics_mod, "_usb_ids_snapshot", lambda include_usb: ["048d:ce00"] if include_usb else [])
    monkeypatch.setattr(diagnostics_mod, "_env_snapshot", lambda: {"KEYRGB_DEBUG": "1"})
    monkeypatch.setattr(diagnostics_mod, "_virt_snapshot", lambda: {"kind": "none"})
    monkeypatch.setattr(diagnostics_mod, "_system_snapshot", lambda: {"os": "linux"})
    monkeypatch.setattr(
        diagnostics_mod, "_system_power_mode_snapshot", lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(diagnostics_mod, "_list_platform_hints", lambda: ["platform-device"])
    monkeypatch.setattr(diagnostics_mod, "_list_module_hints", lambda: ["tuxedo_keyboard"])
    monkeypatch.setattr(diagnostics_mod, "_app_snapshot", lambda: {"version": "test"})
    monkeypatch.setattr(diagnostics_mod, "_power_supply_snapshot", lambda: {"ac_online": True})
    monkeypatch.setattr(
        diagnostics_mod,
        "_backend_probe_snapshot",
        lambda: {
            "selected": "ite8291r3",
            "probes": [
                {"identifiers": {"usb_vid": "0x048d", "usb_pid": "0xce00"}},
                {"identifiers": {"usb_vid": "0xzzzz", "usb_pid": "0xce00"}},
                {"identifiers": {"usb_vid": "0x048d"}},
                {"identifiers": "not-a-dict"},
                "not-a-probe",
            ],
        },
    )

    def fake_usb_devices_snapshot(targets: list[tuple[int, int]]) -> list[dict[str, str]]:
        captured_usb_targets.extend(targets)
        return [{"node": "/dev/hidraw0"}]

    monkeypatch.setattr(diagnostics_mod, "_usb_devices_snapshot", fake_usb_devices_snapshot)
    monkeypatch.setattr(diagnostics_mod, "_config_snapshot", lambda: {"backend": "auto"})
    monkeypatch.setattr(diagnostics_mod, "_process_snapshot", lambda: {"pid": 55})

    diagnostics = diagnostics_mod.collect_diagnostics(include_usb=True)

    assert diagnostics.dmi == {"sys_vendor": "Tongfang"}
    assert diagnostics.system == {"os": "linux"}
    assert diagnostics.hints == {"platform_devices": ["platform-device"], "modules": ["tuxedo_keyboard"]}
    assert list(diagnostics.usb_devices) == [{"node": "/dev/hidraw0"}]
    assert captured_usb_targets == [(0x048D, 0xCE00)]


def test_collect_diagnostics_propagates_programming_errors_from_power_mode_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diagnostics_mod, "_dmi_snapshot", lambda: {"sys_vendor": "Tongfang"})
    monkeypatch.setattr(diagnostics_mod, "_sysfs_leds_snapshot", lambda: ([{"name": "all"}], [{"name": "kbd"}]))
    monkeypatch.setattr(diagnostics_mod, "_usb_ids_snapshot", lambda include_usb: ["048d:ce00"] if include_usb else [])
    monkeypatch.setattr(diagnostics_mod, "_env_snapshot", lambda: {"KEYRGB_DEBUG": "1"})
    monkeypatch.setattr(diagnostics_mod, "_virt_snapshot", lambda: {"kind": "none"})
    monkeypatch.setattr(diagnostics_mod, "_system_snapshot", lambda: {"os": "linux"})
    monkeypatch.setattr(
        diagnostics_mod,
        "_system_power_mode_snapshot",
        lambda: (_ for _ in ()).throw(AssertionError("bug")),
    )
    monkeypatch.setattr(diagnostics_mod, "_list_platform_hints", lambda: [])
    monkeypatch.setattr(diagnostics_mod, "_list_module_hints", lambda: [])
    monkeypatch.setattr(diagnostics_mod, "_app_snapshot", lambda: {"version": "test"})
    monkeypatch.setattr(diagnostics_mod, "_power_supply_snapshot", lambda: {"ac_online": True})
    monkeypatch.setattr(diagnostics_mod, "_backend_probe_snapshot", lambda: {"selected": "ite8291r3", "probes": []})
    monkeypatch.setattr(diagnostics_mod, "_usb_devices_snapshot", lambda targets: [])
    monkeypatch.setattr(diagnostics_mod, "_config_snapshot", lambda: {"backend": "auto"})
    monkeypatch.setattr(diagnostics_mod, "_process_snapshot", lambda: {"pid": 55})

    with pytest.raises(AssertionError, match="bug"):
        diagnostics_mod.collect_diagnostics(include_usb=True)


def test_diagnostics_main_prints_text_and_honors_no_usb(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_include_usb: list[bool] = []

    def fake_collect_diagnostics(*, include_usb: bool) -> Diagnostics:
        captured_include_usb.append(include_usb)
        return _sample_diagnostics()

    monkeypatch.setattr(diagnostics_mod, "collect_diagnostics", fake_collect_diagnostics)
    monkeypatch.setattr(diagnostics_mod, "format_diagnostics_text", lambda diag: "diagnostics text")
    monkeypatch.setattr(sys, "argv", ["keyrgb-diagnostics", "--text", "--no-usb"])

    diagnostics_mod.main()

    assert captured_include_usb == [False]
    assert capsys.readouterr().out == "diagnostics text\n"


def test_diagnostics_main_prints_json_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(diagnostics_mod, "collect_diagnostics", lambda *, include_usb: _sample_diagnostics())
    monkeypatch.setattr(sys, "argv", ["keyrgb-diagnostics"])

    diagnostics_mod.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["app"]["version"] == "test"
    assert payload["backends"]["selected"] == "ite8291r3"


def test_diagnostics_module_trampoline_invokes_package_main(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[bool] = []

    monkeypatch.setattr(diagnostics_mod, "main", lambda: called.append(True))

    runpy.run_module("src.core.diagnostics.__main__", run_name="__main__")

    assert called == [True]


def test_proc_open_holders_returns_empty_when_proc_root_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: RealPath,
) -> None:
    target_path = tmp_path / "device0"
    target_path.write_text("device", encoding="utf-8")

    def fake_path(value: str) -> RealPath:
        if value == "/proc":
            return tmp_path / "missing-proc"
        return RealPath(value)

    monkeypatch.setattr(proc_mod, "Path", fake_path)

    assert proc_open_holders(target_path) == []


def test_proc_open_holders_collects_matching_process_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: RealPath,
) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "not-a-pid").mkdir()
    (proc_root / "4321").mkdir()

    target_real = tmp_path / "real-device"
    target_real.write_text("device", encoding="utf-8")
    target_path = tmp_path / "device-link"
    target_path.symlink_to(target_real)

    holder_pid = 1234
    holder_root = proc_root / str(holder_pid)
    holder_root.mkdir()
    fd_dir = holder_root / "fd"
    fd_dir.mkdir()
    (fd_dir / "0").symlink_to(target_real)
    ignored_fd = fd_dir / "1"
    ignored_fd.symlink_to(tmp_path / "elsewhere")

    (holder_root / "comm").write_text("python\n", encoding="utf-8")
    fake_exe_target = tmp_path / "python-bin"
    fake_exe_target.write_text("", encoding="utf-8")
    (holder_root / "exe").symlink_to(fake_exe_target)
    (holder_root / "cmdline").write_bytes(b"python\x00-m\x00keyrgb\x00")

    real_readlink = os.readlink

    def fake_readlink(path: os.PathLike[str] | str) -> str:
        if str(path).endswith("/1"):
            raise OSError("ignore this fd")
        return real_readlink(path)

    def fake_path(value: str) -> RealPath:
        if value == "/proc":
            return proc_root
        return RealPath(value)

    monkeypatch.setattr(proc_mod, "Path", fake_path)
    monkeypatch.setattr(proc_mod.os, "getpid", lambda: holder_pid)
    monkeypatch.setattr(proc_mod.os, "readlink", fake_readlink)

    holders = proc_open_holders(target_path, limit=5, pid_limit=5)

    assert holders == [
        {
            "pid": holder_pid,
            "is_self": True,
            "comm": "python",
            "exe": str(fake_exe_target),
            "cmdline": "python -m keyrgb",
        }
    ]
