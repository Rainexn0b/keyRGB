from __future__ import annotations

from keyrgb.core.diagnostics.device_discovery import collect_device_discovery


def test_collect_device_discovery_marks_tongfang_lightbar_experimental_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "keyrgb.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": None,
            "probes": [
                {
                    "name": "ite8291_none_chassis_lightbar_tongfang",
                    "available": False,
                    "stability": "experimental",
                    "selection_enabled": False,
                    "selection_reason": "experimental backend disabled",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x6005"},
                }
            ],
        },
    )
    monkeypatch.setattr(
        "keyrgb.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:6005"]
    )
    monkeypatch.setattr(
        "keyrgb.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0x6005",
                "product": "ITE Device(8291)",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr(
        "keyrgb.core.diagnostics.device_discovery.hidraw_devices_snapshot",
        lambda: [{"vendor_id": "0x048d", "product_id": "0x6005", "devnode": "/dev/hidraw3"}],
    )

    payload = collect_device_discovery(include_usb=True)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["status"] == "experimental_disabled"
    assert payload["candidates"][0]["device_type"] == "lightbar"
    assert payload["candidates"][0]["probe_names"] == ["ite8291_none_chassis_lightbar_tongfang"]
    assert payload["candidates"][0]["hidraw_nodes"] == ["/dev/hidraw3"]
