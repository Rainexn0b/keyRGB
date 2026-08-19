"""Unit coverage for ite8291_perkey hidraw discovery and transport helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from keyrgb.core.backends.ite8291_perkey import hidraw, protocol


def test_parse_hid_id_and_uevent_helpers(tmp_path: Path) -> None:
    assert hidraw._parse_hid_id("") is None
    assert hidraw._parse_hid_id("a:b") is None
    assert hidraw._parse_hid_id("0003:ZZZZ:0001") is None
    assert hidraw._parse_hid_id("0003:0000048D:0000600B") == (0x048D, 0x600B)

    uevent = tmp_path / "uevent"
    uevent.write_text("HID_ID=0003:0000048D:0000600B\n\nHID_NAME=ITE\nbadline\n", encoding="utf-8")
    assert hidraw._parse_uevent_file(uevent)["HID_NAME"] == "ITE"
    assert hidraw._parse_uevent_file(tmp_path / "missing") == {}

    hex_path = tmp_path / "idVendor"
    hex_path.write_text("048d\n", encoding="utf-8")
    assert hidraw._read_hex_file(hex_path) == 0x048D
    (tmp_path / "empty").write_text("", encoding="utf-8")
    assert hidraw._read_hex_file(tmp_path / "empty") is None
    (tmp_path / "bad").write_text("nope", encoding="utf-8")
    assert hidraw._read_hex_file(tmp_path / "bad") is None
    assert hidraw._read_hex_file(tmp_path / "nope") is None


def test_find_usb_device_hex_attr_walks_parents(tmp_path: Path) -> None:
    sysfs = tmp_path / "hidraw0"
    device = sysfs / "device"
    parent = tmp_path / "usb1"
    parent.mkdir()
    device.mkdir(parents=True)
    # Make device a symlink-like path by nesting parents via real dirs
    # device.resolve() stays under sysfs/device; put attr on parent of device.
    (device.parent / "bcdDevice").write_text("0003", encoding="utf-8")
    assert hidraw._find_usb_device_hex_attr(sysfs, "bcdDevice") == 0x0003


def test_find_matching_hidraw_device_with_sysfs_tree(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    sysfs_dir = root / "hidraw3"
    device_dir = sysfs_dir / "device"
    device_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)
    (device_dir / "uevent").write_text(
        f"HID_ID=0003:{protocol.VENDOR_ID:08X}:{protocol.SUPPORTED_PRODUCT_IDS[0]:08X}\nHID_NAME=ITE 8291\n",
        encoding="utf-8",
    )
    (dev_root / "hidraw3").write_text("", encoding="utf-8")

    info = hidraw.find_matching_hidraw_device(root=root, dev_root=dev_root)
    assert info is not None
    assert info.hidraw_name == "hidraw3"
    assert info.product_id == protocol.SUPPORTED_PRODUCT_IDS[0]
    assert info.hid_name == "ITE 8291"
    assert info.devnode == dev_root / "hidraw3"


def test_find_matching_hidraw_device_forced_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    node = tmp_path / "forced-hidraw"
    node.write_text("", encoding="utf-8")
    monkeypatch.setenv(protocol.HIDRAW_PATH_ENV, str(node))

    info = hidraw.find_matching_hidraw_device(product_ids=(0x600B,))
    assert info is not None
    assert info.devnode == node
    assert info.product_id == 0x600B
    assert info.hid_id.startswith("forced:")


def test_find_matching_hidraw_device_missing_root(tmp_path: Path) -> None:
    assert hidraw.find_matching_hidraw_device(root=tmp_path / "missing", dev_root=tmp_path) is None


def test_find_matching_skips_bad_and_wrong_ids(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    dev_root.mkdir()

    bad = root / "hidraw0" / "device"
    bad.mkdir(parents=True)
    (bad / "uevent").write_text("HID_ID=bad\n", encoding="utf-8")

    wrong = root / "hidraw1" / "device"
    wrong.mkdir(parents=True)
    (wrong / "uevent").write_text("HID_ID=0003:00001234:00005678\n", encoding="utf-8")

    no_uevent = root / "hidraw2"
    no_uevent.mkdir(parents=True)

    assert hidraw.find_matching_hidraw_device(root=root, dev_root=dev_root) is None


def test_transport_send_write_and_close(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = tmp_path / "hidrawX"
    node.write_text("", encoding="utf-8")

    opens: list[tuple[str, int]] = []
    closed: list[int] = []
    ioctls: list[tuple[Any, ...]] = []
    writes: list[bytes] = []

    monkeypatch.setattr(hidraw.os, "open", lambda path, flags: opens.append((path, flags)) or 11)
    monkeypatch.setattr(hidraw.os, "close", lambda fd: closed.append(fd))
    monkeypatch.setattr(hidraw.os, "write", lambda fd, payload: writes.append(bytes(payload)) or len(payload))
    monkeypatch.setattr(
        hidraw.fcntl,
        "ioctl",
        lambda fd, req, buf, mutate: ioctls.append((fd, req, bytes(buf), mutate)) or 0,
    )
    monkeypatch.setattr(hidraw, "sleep_after_hid_report", lambda **_k: None)

    transport = hidraw.HidrawFeatureOutputTransport(node, backend_name="ite8291_perkey")
    assert opens and opens[0][0] == str(node)

    assert transport.send_feature_report(b"\x01\x02") == 2
    assert ioctls and ioctls[0][0] == 11

    assert transport.write_output_report(b"\x03\x04") == 2
    assert writes == [b"\x03\x04"]

    with pytest.raises(ValueError, match="empty"):
        transport.send_feature_report(b"")
    with pytest.raises(ValueError, match="empty"):
        transport.write_output_report(b"")

    transport.close()
    assert closed == [11]
    transport.close()  # idempotent

    with pytest.raises(RuntimeError, match="closed"):
        transport.send_feature_report(b"\x01")
    with pytest.raises(RuntimeError, match="closed"):
        transport.write_output_report(b"\x01")


def test_transport_del_swallows_close_errors() -> None:
    transport = hidraw.HidrawFeatureOutputTransport.__new__(hidraw.HidrawFeatureOutputTransport)
    transport.devnode = Path("/dev/hidraw-test")
    transport._backend_name = None
    transport._fd = object()  # os.close will TypeError
    transport.__del__()
    assert transport._fd is None


def test_open_matching_hidraw_transport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node = tmp_path / "hidraw9"
    node.write_text("", encoding="utf-8")
    info = hidraw.HidrawDeviceInfo(
        hidraw_name="hidraw9",
        devnode=node,
        sysfs_dir=tmp_path,
        vendor_id=protocol.VENDOR_ID,
        product_id=0x600B,
        hid_id="x",
    )
    monkeypatch.setattr(hidraw, "find_matching_hidraw_device", lambda **_k: info)
    monkeypatch.setattr(hidraw.os, "open", lambda *_a, **_k: 5)
    monkeypatch.setattr(hidraw.os, "close", lambda *_a, **_k: None)

    transport, found = hidraw.open_matching_hidraw_transport(backend_name="ite8291_perkey")
    assert found is info
    assert isinstance(transport, hidraw.HidrawFeatureOutputTransport)
    transport.close()

    monkeypatch.setattr(hidraw, "find_matching_hidraw_device", lambda **_k: None)
    with pytest.raises(FileNotFoundError, match="No hidraw device"):
        hidraw.open_matching_hidraw_transport()


def test_hidiocsfeature_and_cloexec() -> None:
    req = hidraw.hidiocsfeature(8)
    assert isinstance(req, int) and req != 0
    assert hidraw._os_cloexec_flag_or_zero() in {0, int(getattr(__import__("os"), "O_CLOEXEC", 0))}
