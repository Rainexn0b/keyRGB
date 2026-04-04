from __future__ import annotations

from pathlib import Path

import pytest

from src.core.backends.ite8910.hidraw import HidrawFeatureTransport, _parse_hid_id, find_matching_hidraw_device


def test_find_matching_hidraw_device_matches_vid_pid(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    sysfs_dir = root / "hidraw7" / "device"
    sysfs_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)

    (sysfs_dir / "uevent").write_text(
        "DRIVER=hid-generic\nHID_ID=0003:0000048D:00008910\nHID_NAME=ITE Device(829x)\n",
        encoding="utf-8",
    )
    (dev_root / "hidraw7").write_text("", encoding="utf-8")

    info = find_matching_hidraw_device(0x048D, 0x8910, root=root, dev_root=dev_root)

    assert info is not None
    assert info.devnode == dev_root / "hidraw7"
    assert info.vendor_id == 0x048D
    assert info.product_id == 0x8910
    assert info.hid_name == "ITE Device(829x)"


def test_find_matching_hidraw_device_ignores_other_products(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    sysfs_dir = root / "hidraw1" / "device"
    sysfs_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)

    (sysfs_dir / "uevent").write_text(
        "HID_ID=0003:0000048D:0000600B\nHID_NAME=Some Other ITE Device\n",
        encoding="utf-8",
    )
    (dev_root / "hidraw1").write_text("", encoding="utf-8")

    info = find_matching_hidraw_device(0x048D, 0x8910, root=root, dev_root=dev_root)
    assert info is None


def test_parse_hid_id_returns_none_for_malformed_hex() -> None:
    assert _parse_hid_id("0003:not-hex:00008910") is None
    assert _parse_hid_id("0003:0000048D:not-hex") is None


def test_find_matching_hidraw_device_skips_unreadable_uevent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    blocked_uevent = root / "hidraw1" / "device" / "uevent"
    valid_uevent = root / "hidraw2" / "device" / "uevent"
    blocked_uevent.parent.mkdir(parents=True)
    valid_uevent.parent.mkdir(parents=True)
    dev_root.mkdir(parents=True)

    blocked_uevent.write_text("HID_ID=0003:0000048D:00008910\n", encoding="utf-8")
    valid_uevent.write_text(
        "HID_ID=0003:0000048D:00008910\nHID_NAME=ITE Device(8910)\n",
        encoding="utf-8",
    )
    (dev_root / "hidraw2").write_text("", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == blocked_uevent:
            raise PermissionError("denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    info = find_matching_hidraw_device(0x048D, 0x8910, root=root, dev_root=dev_root)

    assert info is not None
    assert info.hidraw_name == "hidraw2"
    assert info.devnode == dev_root / "hidraw2"
    assert info.hid_name == "ITE Device(8910)"


@pytest.mark.parametrize("fd", [object(), -1], ids=["bad-fd-type", "bad-fd-oserror"])
def test_hidraw_feature_transport_del_swallows_cleanup_failures(fd: object) -> None:
    transport = HidrawFeatureTransport.__new__(HidrawFeatureTransport)
    transport.devnode = Path("/dev/hidraw-test")
    transport._fd = fd

    transport.__del__()

    assert transport._fd is None
