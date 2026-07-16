from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.backends import shared_hidraw_probe as probe
from src.core.backends.ite8291_perkey import hidraw as ite8291_hidraw


def test_usb_scan_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_DISABLE_USB_SCAN", raising=False)
    assert probe.usb_scan_disabled() is False
    monkeypatch.setenv("KEYRGB_DISABLE_USB_SCAN", "1")
    assert probe.usb_scan_disabled() is True


def test_identifiers_for_hidraw_match_includes_hid_name() -> None:
    match = SimpleNamespace(
        vendor_id=0x048D,
        product_id=0xC195,
        devnode=Path("/dev/hidraw3"),
        hid_name="ITE Device",
    )
    assert probe.identifiers_for_hidraw_match(match) == {
        "usb_vid": "0x048d",
        "usb_pid": "0xc195",
        "hidraw": "/dev/hidraw3",
        "hid_name": "ITE Device",
    }


def test_identifiers_for_hidraw_match_omits_empty_hid_name() -> None:
    match = SimpleNamespace(
        vendor_id=0x048D,
        product_id=0xC197,
        devnode=Path("/dev/hidraw1"),
        hid_name="",
    )
    assert probe.identifiers_for_hidraw_match(match) == {
        "usb_vid": "0x048d",
        "usb_pid": "0xc197",
        "hidraw": "/dev/hidraw1",
    }


def test_identifiers_for_hidraw_match_can_include_bcd_device() -> None:
    match = SimpleNamespace(
        vendor_id=0x048D,
        product_id=0xCE00,
        devnode=Path("/dev/hidraw2"),
        hid_name="ITE",
        bcd_device=0x0002,
    )
    assert probe.identifiers_for_hidraw_match(match, include_bcd_device=True) == {
        "usb_vid": "0x048d",
        "usb_pid": "0xce00",
        "hidraw": "/dev/hidraw2",
        "hid_name": "ITE",
        "usb_bcd_device": "0x0002",
    }


def test_open_matching_raises_when_no_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe, "find_matching_ite8291_style_hidraw_device", lambda **_kwargs: None)
    with pytest.raises(FileNotFoundError, match="ITE 8258"):
        probe.open_matching_ite8291_style_hidraw_transport(
            product_ids=(0xC195,),
            forced_path_env="KEYRGB_ITE8258_HIDRAW_PATH",
            backend_name="ite8258_zones_lenovo_legion",
            vendor_id=0x048D,
            missing_label="ITE 8258",
        )


def test_find_matching_ite8910_style_uses_forced_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forced = tmp_path / "hidraw3"
    forced.write_text("", encoding="utf-8")
    monkeypatch.setenv("KEYRGB_TEST_HIDRAW_PATH", str(forced))
    created: list[dict[str, object]] = []

    def _factory(**kwargs: object) -> SimpleNamespace:
        created.append(kwargs)
        return SimpleNamespace(**kwargs)

    match = probe.find_matching_ite8910_style_hidraw_device(
        vendor_id=0x048D,
        product_ids=(0x8297,),
        forced_path_env="KEYRGB_TEST_HIDRAW_PATH",
        forced_product_id=0x8297,
        find_matching_fn=lambda *_a: None,
        device_info_factory=_factory,
    )
    assert match is not None
    assert match.devnode == forced
    assert created[0]["product_id"] == 0x8297


def test_find_matching_ite8910_style_falls_back_to_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_TEST_HIDRAW_PATH", "/tmp/does-not-exist")
    dummy = SimpleNamespace(product_id=0x7001)

    match = probe.find_matching_ite8910_style_hidraw_device(
        vendor_id=0x048D,
        product_ids=(0x6010, 0x7001),
        forced_path_env="KEYRGB_TEST_HIDRAW_PATH",
        forced_product_id=0x7001,
        find_matching_fn=lambda _vid, pid: dummy if pid == 0x7001 else None,
        device_info_factory=lambda **_k: SimpleNamespace(),
    )
    assert match is dummy


def test_open_matching_builds_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    info = SimpleNamespace(devnode=Path("/dev/hidraw9"), vendor_id=0x048D, product_id=0xC195)
    created: list[tuple[Path, str | None]] = []

    class _FakeTransport:
        def __init__(self, devnode: Path, *, backend_name: str | None = None) -> None:
            created.append((devnode, backend_name))

    monkeypatch.setattr(probe, "find_matching_ite8291_style_hidraw_device", lambda **_kwargs: info)
    monkeypatch.setattr(ite8291_hidraw, "HidrawFeatureOutputTransport", _FakeTransport)

    transport, match = probe.open_matching_ite8291_style_hidraw_transport(
        product_ids=(0xC195,),
        forced_path_env="KEYRGB_ITE8258_HIDRAW_PATH",
        backend_name="ite8258_zones_lenovo_legion",
        vendor_id=0x048D,
        missing_label="ITE 8258",
    )
    assert match is info
    assert isinstance(transport, _FakeTransport)
    assert created == [(Path("/dev/hidraw9"), "ite8258_zones_lenovo_legion")]
