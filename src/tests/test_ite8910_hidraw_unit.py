from __future__ import annotations

from pathlib import Path

from src.core.backends.ite8910.hidraw import find_matching_hidraw_device


def test_find_matching_hidraw_device_matches_vid_pid(tmp_path: Path) -> None:
    root = tmp_path / "sys" / "class" / "hidraw"
    dev_root = tmp_path / "dev"
    sysfs_dir = root / "hidraw7" / "device"
    sysfs_dir.mkdir(parents=True)
    dev_root.mkdir(parents=True)

    (sysfs_dir / "uevent").write_text(
        "DRIVER=hid-generic\n" "HID_ID=0003:0000048D:00008910\n" "HID_NAME=ITE Device(829x)\n",
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
        "HID_ID=0003:0000048D:0000600B\n" "HID_NAME=Some Other ITE Device\n",
        encoding="utf-8",
    )
    (dev_root / "hidraw1").write_text("", encoding="utf-8")

    info = find_matching_hidraw_device(0x048D, 0x8910, root=root, dev_root=dev_root)
    assert info is None
