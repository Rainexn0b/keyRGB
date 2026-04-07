from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import src.core.diagnostics.collectors.system as collectors_system
import src.core.power.system as power_system


def _patch_module_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    replacements: dict[str, Path],
) -> None:
    real_path = Path

    def fake_path(value: str | Path) -> Path:
        text = str(value)
        if text in replacements:
            return replacements[text]
        return real_path(value)

    monkeypatch.setattr(collectors_system, "Path", fake_path)


def test_list_platform_hints_filters_sorts_and_caps_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    platform_root = tmp_path / "platform-devices"
    platform_root.mkdir()

    for index in range(82):
        (platform_root / f"tuxedo-{index:02d}").mkdir()
    (platform_root / "generic-device").mkdir()
    (platform_root / "ITE-bridge").mkdir()

    _patch_module_path(monkeypatch, replacements={"/sys/bus/platform/devices": platform_root})

    hints = collectors_system.list_platform_hints()

    assert len(hints) == 80
    assert hints[0] == "ITE-bridge"
    assert hints[-1] == "tuxedo-78"
    assert "generic-device" not in hints


def test_list_platform_hints_returns_empty_on_iteration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_path = Path

    class BrokenRoot:
        def exists(self) -> bool:
            return True

        def iterdir(self) -> list[Path]:
            raise OSError("platform devices unavailable")

    def fake_path(value: str | Path) -> Path | BrokenRoot:
        if str(value) == "/sys/bus/platform/devices":
            return BrokenRoot()
        return real_path(value)

    monkeypatch.setattr(collectors_system, "Path", fake_path)

    assert collectors_system.list_platform_hints() == []


def test_list_module_hints_filters_uniques_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    modules_path = tmp_path / "modules"
    modules_path.write_text(
        "\n".join(
            [
                "snd_hda_intel 0 0 - Live 0x0000",
                "tuxedo_keyboard 0 0 - Live 0x0001",
                "hid_generic 0 0 - Live 0x0002",
                "hid_generic 0 0 - Live 0x0003",
                "hid_multitouch 0 0 - Live 0x0004",
                "acpi_call 0 0 - Live 0x0005",
            ]
        ),
        encoding="utf-8",
    )

    _patch_module_path(monkeypatch, replacements={"/proc/modules": modules_path})

    hints = collectors_system.list_module_hints()

    assert hints == ["tuxedo_keyboard", "hid_generic", "hid_multitouch", "acpi_call"]


def test_list_module_hints_returns_empty_on_read_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_path = Path

    class BrokenModulesPath:
        def exists(self) -> bool:
            return True

        def read_text(self, *, encoding: str, errors: str) -> str:
            raise OSError("cannot read modules")

    def fake_path(value: str | Path) -> Path | BrokenModulesPath:
        if str(value) == "/proc/modules":
            return BrokenModulesPath()
        return real_path(value)

    monkeypatch.setattr(collectors_system, "Path", fake_path)

    assert collectors_system.list_module_hints() == []


def test_power_supply_snapshot_collects_non_empty_device_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    power_root = tmp_path / "power-supply"
    ac_dir = power_root / "AC"
    bat_dir = power_root / "BAT0"
    ac_dir.mkdir(parents=True)
    bat_dir.mkdir(parents=True)
    (power_root / "README").write_text("ignore", encoding="utf-8")

    (ac_dir / "type").write_text("Mains\n", encoding="utf-8")
    (ac_dir / "online").write_text("1\n", encoding="utf-8")

    (bat_dir / "type").write_text("Battery\n", encoding="utf-8")
    (bat_dir / "status").write_text("Discharging\n", encoding="utf-8")
    (bat_dir / "capacity").write_text("85\n", encoding="utf-8")
    (bat_dir / "energy_now").write_text("\n", encoding="utf-8")

    _patch_module_path(monkeypatch, replacements={"/sys/class/power_supply": power_root})

    snapshot = collectors_system.power_supply_snapshot()

    assert snapshot == {
        "AC": {"type": "Mains", "online": "1"},
        "BAT0": {
            "type": "Battery",
            "status": "Discharging",
            "capacity": "85",
        },
    }


def test_power_supply_snapshot_returns_empty_on_sysfs_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_path = Path

    class BrokenPowerRoot:
        def exists(self) -> bool:
            return True

        def iterdir(self) -> list[Path]:
            raise OSError("power supply root unavailable")

    def fake_path(value: str | Path) -> Path | BrokenPowerRoot:
        if str(value) == "/sys/class/power_supply":
            return BrokenPowerRoot()
        return real_path(value)

    monkeypatch.setattr(collectors_system, "Path", fake_path)

    assert collectors_system.power_supply_snapshot() == {}


def test_repo_version_text_reads_project_version_from_pyproject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.black]",
                'version = "ignored"',
                "",
                "[project]",
                'name = "keyrgb"',
                'version = "1.2.3" # current release',
                "",
                "[tool.pytest.ini_options]",
                'version = "ignored-again"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(collectors_system, "repo_root_from", lambda _anchor: tmp_path)

    version = collectors_system._repo_version_text("ignored-anchor")

    assert version == "1.2.3"


def test_repo_version_text_returns_none_without_pyproject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(collectors_system, "repo_root_from", lambda _anchor: tmp_path)

    assert collectors_system._repo_version_text("ignored-anchor") is None


def test_repo_version_text_returns_none_for_malformed_project_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "keyrgb"',
                "version = 1.2.3",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(collectors_system, "repo_root_from", lambda _anchor: tmp_path)

    assert collectors_system._repo_version_text("ignored-anchor") is None


def test_app_snapshot_prefers_repo_version_and_reports_installed_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collectors_system, "_repo_version_text", lambda _anchor: "1.2.3")

    def fake_version(dist_name: str) -> str:
        if dist_name == "Keyrgb":
            return "9.9.9"
        raise collectors_system.metadata.PackageNotFoundError(dist_name)

    monkeypatch.setattr(collectors_system.metadata, "version", fake_version)

    snapshot = collectors_system.app_snapshot()

    assert snapshot == {
        "version": "1.2.3",
        "version_source": "pyproject",
        "dist_name": "Keyrgb",
        "dist_version": "9.9.9",
    }


def test_app_snapshot_falls_back_to_distribution_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collectors_system, "_repo_version_text", lambda _anchor: None)

    def fake_version(dist_name: str) -> str:
        if dist_name == "KeyRGB":
            return "2.5.0"
        raise collectors_system.metadata.PackageNotFoundError(dist_name)

    monkeypatch.setattr(collectors_system.metadata, "version", fake_version)

    snapshot = collectors_system.app_snapshot()

    assert snapshot == {
        "version": "2.5.0",
        "dist": "KeyRGB",
        "version_source": "dist",
    }


def test_system_snapshot_collects_platform_python_and_filtered_os_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        collectors_system.read_kv_file,
        "__call__",
        collectors_system.read_kv_file.__call__,
        raising=False,
    )
    monkeypatch.setattr(
        collectors_system,
        "read_kv_file",
        lambda _path: {
            "NAME": "Fedora Linux",
            "PRETTY_NAME": "Fedora Linux 42",
            "ID": "fedora",
            "VERSION_ID": "42",
            "VARIANT_ID": "kde",
            "BUG_REPORT_URL": "https://example.invalid",
        },
    )
    monkeypatch.setattr(
        __import__("platform"),
        "uname",
        lambda: SimpleNamespace(release="6.8.12", machine="x86_64"),
    )
    monkeypatch.setattr(sys, "version", "3.12.2 custom-build", raising=False)

    snapshot = collectors_system.system_snapshot()

    assert snapshot == {
        "kernel_release": "6.8.12",
        "machine": "x86_64",
        "python": "3.12.2",
        "os_release": {
            "NAME": "Fedora Linux",
            "PRETTY_NAME": "Fedora Linux 42",
            "ID": "fedora",
            "VERSION_ID": "42",
            "VARIANT_ID": "kde",
        },
    }


def test_system_snapshot_tolerates_uname_and_python_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BadVersion:
        def split(self) -> list[str]:
            raise RuntimeError("python version unavailable")

    monkeypatch.setattr(collectors_system, "read_kv_file", lambda _path: {"ID": "fedora", "BUG_REPORT_URL": "x"})
    monkeypatch.setattr(__import__("platform"), "uname", lambda: (_ for _ in ()).throw(RuntimeError("uname failed")))
    monkeypatch.setattr(sys, "version", BadVersion(), raising=False)

    snapshot = collectors_system.system_snapshot()

    assert snapshot == {"os_release": {"ID": "fedora"}}


def test_system_power_mode_snapshot_reports_status(monkeypatch: pytest.MonkeyPatch) -> None:
    status = SimpleNamespace(
        supported=True,
        mode=SimpleNamespace(value="balanced"),
        reason="ok",
        identifiers={"cpufreq_root": "/fake/cpufreq", "can_apply": "true"},
    )
    monkeypatch.setattr(power_system, "get_status", lambda: status)

    snapshot = collectors_system.system_power_mode_snapshot()

    assert snapshot == {
        "supported": True,
        "mode": "balanced",
        "reason": "ok",
        "identifiers": {"cpufreq_root": "/fake/cpufreq", "can_apply": "true"},
    }


def test_system_power_mode_snapshot_reports_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def raise_status() -> SimpleNamespace:
        raise RuntimeError("status unavailable")

    monkeypatch.setattr(power_system, "get_status", raise_status)

    with caplog.at_level(logging.DEBUG, logger=collectors_system.__name__):
        snapshot = collectors_system.system_power_mode_snapshot()

    assert snapshot["supported"] is False
    assert snapshot["mode"] == "unknown"
    assert snapshot["reason"] == "error"
    assert "status unavailable" in snapshot["error"]
    assert "Failed to collect system power mode diagnostics" in caplog.text
