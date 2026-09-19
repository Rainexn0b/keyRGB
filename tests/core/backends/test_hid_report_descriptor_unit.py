from __future__ import annotations

from keyrgb.core.backends.hid_report_descriptor import application_collection_usage
from keyrgb.core.backends.ite8291_none_chassis_lightbar_tongfang.backend import _select_usage_matched_hidraw
from keyrgb.core.backends.ite8291_perkey.hidraw import HidrawDeviceInfo


def _application_descriptor(*, usage_page: int, usage: int) -> bytes:
    page = int(usage_page).to_bytes(2, "little")
    return bytes((0x06, page[0], page[1], 0x09, int(usage) & 0xFF, 0xA1, 0x01, 0xC0))


def test_application_collection_usage_reads_openrgb_ionico_identifiers() -> None:
    descriptor = _application_descriptor(usage_page=0xFF03, usage=0x01)

    assert application_collection_usage(descriptor) == (0xFF03, 0x01)


def test_application_collection_usage_returns_none_without_application_collection() -> None:
    assert application_collection_usage(b"\x05\x01\x09\x06") is None


def test_select_usage_matched_hidraw_prefers_expected_usage(tmp_path) -> None:
    wrong = tmp_path / "hidraw0"
    right = tmp_path / "hidraw1"
    (wrong / "device").mkdir(parents=True)
    (right / "device").mkdir(parents=True)
    (wrong / "device" / "report_descriptor").write_bytes(_application_descriptor(usage_page=0x0001, usage=0x06))
    (right / "device" / "report_descriptor").write_bytes(_application_descriptor(usage_page=0xFF03, usage=0x01))

    matches = (
        HidrawDeviceInfo(
            hidraw_name="hidraw0",
            devnode=tmp_path / "hidraw0",
            sysfs_dir=wrong,
            vendor_id=0x048D,
            product_id=0x6005,
            hid_id="0003:048D:6005",
        ),
        HidrawDeviceInfo(
            hidraw_name="hidraw1",
            devnode=tmp_path / "hidraw1",
            sysfs_dir=right,
            vendor_id=0x048D,
            product_id=0x6005,
            hid_id="0003:048D:6005",
        ),
    )

    selected = _select_usage_matched_hidraw(matches)

    assert selected is not None
    assert selected.hidraw_name == "hidraw1"


def test_select_usage_matched_hidraw_fails_closed_when_multiple_nodes_mismatch(tmp_path) -> None:
    first = tmp_path / "hidraw0"
    second = tmp_path / "hidraw1"
    (first / "device").mkdir(parents=True)
    (second / "device").mkdir(parents=True)
    (first / "device" / "report_descriptor").write_bytes(_application_descriptor(usage_page=0x0001, usage=0x06))
    (second / "device" / "report_descriptor").write_bytes(_application_descriptor(usage_page=0x0001, usage=0x02))

    matches = (
        HidrawDeviceInfo(
            hidraw_name="hidraw0",
            devnode=tmp_path / "hidraw0",
            sysfs_dir=first,
            vendor_id=0x048D,
            product_id=0x6005,
            hid_id="0003:048D:6005",
        ),
        HidrawDeviceInfo(
            hidraw_name="hidraw1",
            devnode=tmp_path / "hidraw1",
            sysfs_dir=second,
            vendor_id=0x048D,
            product_id=0x6005,
            hid_id="0003:048D:6005",
        ),
    )

    assert _select_usage_matched_hidraw(matches) is None
