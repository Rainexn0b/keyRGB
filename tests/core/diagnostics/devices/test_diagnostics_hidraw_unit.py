from __future__ import annotations

from pathlib import Path

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.core.diagnostics.hidraw as hidraw


def test_read_hidraw_report_descriptor_reads_size_and_payload(monkeypatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(hidraw.os, "open", lambda path, flags: 99)
    monkeypatch.setattr(hidraw.os, "close", lambda fd: calls.append(fd))

    def fake_ioctl(fd, code, buf, mutate):
        assert fd == 99
        assert mutate is True
        if code == hidraw.hidiocgrdescsize():
            buf[0] = 4
            return 0
        if code == hidraw.hidiocgrdesc(4):
            buf[0:4] = (4).to_bytes(4, "little")
            buf[4:8] = bytes.fromhex("05010906")
            return 0
        raise AssertionError(f"unexpected ioctl code: {code}")

    monkeypatch.setattr(hidraw.fcntl, "ioctl", fake_ioctl)

    payload = hidraw.read_hidraw_report_descriptor(Path("/dev/hidraw7"))

    assert payload == {
        "report_descriptor_size": 4,
        "report_descriptor_hex": "05010906",
    }
    assert calls == [99]


def test_read_hidraw_report_descriptor_returns_error_text(monkeypatch) -> None:
    monkeypatch.setattr(hidraw.os, "open", lambda path, flags: (_ for _ in ()).throw(PermissionError("denied")))

    payload = hidraw.read_hidraw_report_descriptor(Path("/dev/hidraw7"))

    assert payload == {"report_descriptor_error": "denied"}


def test_hidraw_devices_snapshot_includes_descriptor_info(monkeypatch, tmp_path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    hidraw_dir = root / "hidraw3" / "device"
    hidraw_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)
    (hidraw_dir / "uevent").write_text("HID_ID=0003:0000048D:00007001\nHID_NAME=ITE Device(8233)\n", encoding="utf-8")
    (dev_root / "hidraw3").write_bytes(b"")

    monkeypatch.setattr(hidraw.os, "access", lambda path, mode: True)
    monkeypatch.setattr(
        hidraw,
        "read_hidraw_report_descriptor",
        lambda path: {"report_descriptor_size": 16, "report_descriptor_hex": "aa55"},
    )

    payload = hidraw.hidraw_devices_snapshot(root=root, dev_root=dev_root)

    assert payload == [
        {
            "hidraw_name": "hidraw3",
            "devnode": str(dev_root / "hidraw3"),
            "sysfs_dir": str(root / "hidraw3"),
            "hid_id": "0003:0000048D:00007001",
            "hid_name": "ITE Device(8233)",
            "vendor_id": "0x048d",
            "product_id": "0x7001",
            "access": {"read": True, "write": True},
            "report_descriptor_size": 16,
            "report_descriptor_hex": "aa55",
        }
    ]


def test_hidraw_devices_snapshot_returns_partial_payload_on_access_error(monkeypatch, tmp_path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    first_dir = root / "hidraw1" / "device"
    second_dir = root / "hidraw2" / "device"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)
    (first_dir / "uevent").write_text("HID_ID=0003:0000048D:00007001\nHID_NAME=ITE Device(1)\n", encoding="utf-8")
    (second_dir / "uevent").write_text("HID_ID=0003:0000048D:00007002\nHID_NAME=ITE Device(2)\n", encoding="utf-8")
    (dev_root / "hidraw1").write_bytes(b"")
    (dev_root / "hidraw2").write_bytes(b"")

    def fake_access(path, mode):
        if Path(path).name == "hidraw2":
            raise PermissionError("hidraw2 denied")
        return True

    monkeypatch.setattr(hidraw.os, "access", fake_access)
    monkeypatch.setattr(
        hidraw,
        "read_hidraw_report_descriptor",
        lambda path: {"report_descriptor_size": 16, "report_descriptor_hex": "aa55"},
    )

    payload = hidraw.hidraw_devices_snapshot(root=root, dev_root=dev_root)

    assert payload == [
        {
            "hidraw_name": "hidraw1",
            "devnode": str(dev_root / "hidraw1"),
            "sysfs_dir": str(root / "hidraw1"),
            "hid_id": "0003:0000048D:00007001",
            "hid_name": "ITE Device(1)",
            "vendor_id": "0x048d",
            "product_id": "0x7001",
            "access": {"read": True, "write": True},
            "report_descriptor_size": 16,
            "report_descriptor_hex": "aa55",
        }
    ]
