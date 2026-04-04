from __future__ import annotations

from pathlib import Path

import pytest

from src.core.diagnostics.paths import (
    config_file_path,
    sysfs_dmi_root,
    sysfs_leds_root,
    sysfs_usb_devices_root,
    usb_devnode_root,
)
from src.core.diagnostics.usb import usb_devices_snapshot
import src.core.diagnostics.paths as paths_mod
import src.core.diagnostics.usb as usb_mod


def test_diagnostics_paths_use_expected_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KEYRGB_SYSFS_DMI_ROOT", raising=False)
    monkeypatch.delenv("KEYRGB_SYSFS_LEDS_ROOT", raising=False)
    monkeypatch.delenv("KEYRGB_SYSFS_USB_ROOT", raising=False)
    monkeypatch.delenv("KEYRGB_USB_DEVNODE_ROOT", raising=False)
    monkeypatch.delenv("KEYRGB_CONFIG_PATH", raising=False)
    monkeypatch.delenv("KEYRGB_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(paths_mod.Path, "home", lambda: tmp_path)

    assert sysfs_dmi_root() == Path("/sys/class/dmi/id")
    assert sysfs_leds_root() == Path("/sys/class/leds")
    assert sysfs_usb_devices_root() == Path("/sys/bus/usb/devices")
    assert usb_devnode_root() == Path("/dev/bus/usb")
    assert config_file_path() == tmp_path / ".config" / "keyrgb" / "config.json"


def test_diagnostics_paths_honor_override_precedence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KEYRGB_CONFIG_PATH", raising=False)
    monkeypatch.delenv("KEYRGB_CONFIG_DIR", raising=False)
    monkeypatch.setenv("KEYRGB_SYSFS_DMI_ROOT", str(tmp_path / "dmi"))
    monkeypatch.setenv("KEYRGB_SYSFS_LEDS_ROOT", str(tmp_path / "leds"))
    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(tmp_path / "usb"))
    monkeypatch.setenv("KEYRGB_USB_DEVNODE_ROOT", str(tmp_path / "bus"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert sysfs_dmi_root() == tmp_path / "dmi"
    assert sysfs_leds_root() == tmp_path / "leds"
    assert sysfs_usb_devices_root() == tmp_path / "usb"
    assert usb_devnode_root() == tmp_path / "bus"
    assert config_file_path() == tmp_path / "xdg" / "keyrgb" / "config.json"

    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfgdir"))
    assert config_file_path() == tmp_path / "cfgdir" / "config.json"

    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "explicit.json"))
    assert config_file_path() == tmp_path / "explicit.json"


def test_usb_devices_snapshot_handles_empty_targets_and_missing_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(tmp_path / "missing-usb-root"))

    assert usb_devices_snapshot([]) == []
    assert usb_devices_snapshot([(0x048D, 0xCE00)]) == []


def test_usb_devices_snapshot_collects_matching_device_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    usb_root = tmp_path / "sysfs-usb"
    dev_root = tmp_path / "dev-bus-usb"
    drivers_root = tmp_path / "drivers"
    usb_root.mkdir()
    dev_root.mkdir()
    drivers_root.mkdir()

    dev = usb_root / "1-2"
    dev.mkdir()
    (dev / "idVendor").write_text("048d\n", encoding="utf-8")
    (dev / "idProduct").write_text("ce00\n", encoding="utf-8")
    (dev / "manufacturer").write_text("ITE\n", encoding="utf-8")
    (dev / "product").write_text("Gaming Keyboard\n", encoding="utf-8")
    (dev / "serial").write_text("ABC123\n", encoding="utf-8")
    (dev / "bcdDevice").write_text("1.00\n", encoding="utf-8")
    (dev / "speed").write_text("12\n", encoding="utf-8")
    (dev / "busnum").write_text("1\n", encoding="utf-8")
    (dev / "devnum").write_text("2\n", encoding="utf-8")
    driver_target = drivers_root / "ite-kbd"
    driver_target.mkdir()
    (dev / "driver").symlink_to(driver_target)

    ignored = usb_root / "2-9"
    ignored.mkdir()
    (ignored / "idVendor").write_text("zzzz\n", encoding="utf-8")
    (ignored / "idProduct").write_text("0001\n", encoding="utf-8")

    devnode = dev_root / "001" / "002"
    devnode.parent.mkdir(parents=True)
    devnode.write_text("", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(usb_root))
    monkeypatch.setenv("KEYRGB_USB_DEVNODE_ROOT", str(dev_root))
    monkeypatch.setattr(usb_mod.os, "access", lambda path, mode: mode == usb_mod.os.R_OK)
    monkeypatch.setattr(
        usb_mod,
        "proc_open_holders",
        lambda path: [
            {"pid": 100, "is_self": True, "comm": "pytest"},
            {"pid": 200, "is_self": False, "comm": "openrgb"},
        ],
    )

    snapshot = usb_devices_snapshot([(0x048D, 0xCE00)])

    assert len(snapshot) == 1
    entry = snapshot[0]
    assert entry["sysfs_path"] == str(dev)
    assert entry["idVendor"] == "0x048d"
    assert entry["idProduct"] == "0xce00"
    assert entry["manufacturer"] == "ITE"
    assert entry["product"] == "Gaming Keyboard"
    assert entry["serial"] == "ABC123"
    assert entry["bcdDevice"] == "1.00"
    assert entry["speed"] == "12"
    assert entry["busnum"] == "1"
    assert entry["devnum"] == "2"
    assert entry["devnode"] == str(devnode)
    assert entry["devnode_mode"] == oct(int(devnode.stat().st_mode) & 0o777)
    assert entry["devnode_uid"] == int(devnode.stat().st_uid)
    assert entry["devnode_gid"] == int(devnode.stat().st_gid)
    assert entry["devnode_access"] == {"read": True, "write": False}
    assert entry["devnode_open_by"][1]["comm"] == "openrgb"
    assert entry["devnode_open_by_others"] == [{"pid": 200, "is_self": False, "comm": "openrgb"}]
    assert entry["driver"] == "ite-kbd"


def test_usb_devices_snapshot_marks_missing_devnode_without_failing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    usb_root = tmp_path / "sysfs-usb"
    usb_root.mkdir()

    dev = usb_root / "3-4"
    dev.mkdir()
    (dev / "idVendor").write_text("048d\n", encoding="utf-8")
    (dev / "idProduct").write_text("ce00\n", encoding="utf-8")
    (dev / "busnum").write_text("3\n", encoding="utf-8")
    (dev / "devnum").write_text("4\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(usb_root))
    monkeypatch.setenv("KEYRGB_USB_DEVNODE_ROOT", str(tmp_path / "missing-devroot"))

    snapshot = usb_devices_snapshot([(0x048D, 0xCE00)])

    assert snapshot == [
        {
            "sysfs_path": str(dev),
            "idVendor": "0x048d",
            "idProduct": "0xce00",
            "busnum": "3",
            "devnum": "4",
            "devnode": str(tmp_path / "missing-devroot" / "003" / "004"),
            "devnode_exists": False,
        }
    ]


def test_usb_devices_snapshot_ignores_devnode_and_driver_runtime_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    usb_root = tmp_path / "sysfs-usb"
    dev_root = tmp_path / "dev-bus-usb"
    drivers_root = tmp_path / "drivers"
    usb_root.mkdir()
    dev_root.mkdir()
    drivers_root.mkdir()

    dev = usb_root / "1-2"
    dev.mkdir()
    (dev / "idVendor").write_text("048d\n", encoding="utf-8")
    (dev / "idProduct").write_text("ce00\n", encoding="utf-8")
    (dev / "busnum").write_text("1\n", encoding="utf-8")
    (dev / "devnum").write_text("2\n", encoding="utf-8")
    driver_target = drivers_root / "ite-kbd"
    driver_target.mkdir()
    (dev / "driver").symlink_to(driver_target)

    devnode = dev_root / "001" / "002"
    devnode.parent.mkdir(parents=True)
    devnode.write_text("", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(usb_root))
    monkeypatch.setenv("KEYRGB_USB_DEVNODE_ROOT", str(dev_root))
    monkeypatch.setattr(usb_mod.os, "access", lambda path, mode: True)
    monkeypatch.setattr(
        usb_mod,
        "proc_open_holders",
        lambda path: (_ for _ in ()).throw(RuntimeError("holders boom")),
    )

    original_resolve = Path.resolve

    def resolve_with_driver_failure(self: Path, strict: bool = False) -> Path:
        if self == dev / "driver":
            raise RuntimeError("driver loop")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", resolve_with_driver_failure)

    snapshot = usb_devices_snapshot([(0x048D, 0xCE00)])

    assert len(snapshot) == 1
    entry = snapshot[0]
    assert entry["sysfs_path"] == str(dev)
    assert entry["devnode"] == str(devnode)
    assert "devnode_access" in entry
    assert "devnode_open_by" not in entry
    assert "driver" not in entry


def test_usb_devices_snapshot_returns_partial_results_when_iteration_step_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    usb_root = tmp_path / "sysfs-usb"
    usb_root.mkdir()

    first = usb_root / "1-1"
    first.mkdir()
    (first / "idVendor").write_text("048d\n", encoding="utf-8")
    (first / "idProduct").write_text("ce00\n", encoding="utf-8")

    second = usb_root / "2-2"
    second.mkdir()
    (second / "idVendor").write_text("048d\n", encoding="utf-8")
    (second / "idProduct").write_text("ce00\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_SYSFS_USB_ROOT", str(usb_root))

    original_read_text = usb_mod.read_text

    def read_text_with_iteration_failure(path: Path):
        if path.parent == second and path.name == "idVendor":
            raise RuntimeError("iteration boom")
        return original_read_text(path)

    monkeypatch.setattr(usb_mod, "read_text", read_text_with_iteration_failure)

    assert usb_devices_snapshot([(0x048D, 0xCE00)]) == [
        {
            "sysfs_path": str(first),
            "idVendor": "0x048d",
            "idProduct": "0xce00",
        }
    ]
