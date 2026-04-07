from __future__ import annotations

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.diagnostics.device_discovery import collect_device_discovery, format_device_discovery_text


def test_collect_device_discovery_marks_experimental_disabled_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": "ite8291r3",
            "probes": [
                {
                    "name": "ite8233",
                    "available": False,
                    "stability": "experimental",
                    "selection_enabled": False,
                    "selection_reason": "experimental backend disabled",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x7001"},
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:7001"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0x7001",
                "product": "ITE Device(8233)",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.hidraw_devices_snapshot",
        lambda: [{"vendor_id": "0x048d", "product_id": "0x7001", "devnode": "/dev/hidraw1"}],
    )

    payload = collect_device_discovery(include_usb=True)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["status"] == "experimental_disabled"
    assert payload["candidates"][0]["device_type"] == "lightbar"
    assert payload["candidates"][0]["probe_names"] == ["ite8233"]
    assert payload["candidates"][0]["hidraw_nodes"] == ["/dev/hidraw1"]
    assert payload["support_actions"]["recommended_issue_template"] == "hardware-support"
    assert payload["support_actions"]["optional_capture_commands"] == [
        "lsusb -v -d 048d:7001",
        "sudo usbhid-dump -d 048d:7001 -e descriptor",
    ]


def test_collect_device_discovery_flags_unrecognized_ite_device(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {"selected": None, "probes": []},
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:1234"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0x1234",
                "product": "ITE Mystery Device",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.hidraw_devices_snapshot", lambda: [])

    payload = collect_device_discovery(include_usb=True)

    assert payload["candidates"][0]["status"] == "unrecognized_ite"
    assert payload["candidates"][0]["device_type"] == "unknown"
    assert "support issue" in payload["candidates"][0]["recommended_action"].lower()


def test_format_device_discovery_text_includes_candidates() -> None:
    text = format_device_discovery_text(
        {
            "selected_backend": "ite8291r3",
            "usb_ids": ["048d:600b", "048d:7001"],
            "summary": {"candidate_count": 1, "supported_count": 0, "attention_count": 1},
            "support_actions": {
                "recommended_issue_template": "hardware-support",
                "recommended_issue_url": "https://example.invalid/hardware-support",
                "next_steps": ["Attach the support bundle."],
                "optional_capture_commands": ["lsusb -v -d 048d:7001"],
            },
            "candidates": [
                {
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "product": "ITE Device(8233)",
                    "device_type": "lightbar",
                    "status": "experimental_disabled",
                    "recommended_action": "Enable experimental backends and retry.",
                    "probe_names": ["ite8233"],
                    "hidraw_nodes": ["/dev/hidraw1"],
                }
            ],
        }
    )

    assert "Device discovery:" in text
    assert "0x048d:0x7001 ITE Device(8233) type=lightbar status=experimental_disabled" in text
    assert "Enable experimental backends and retry." in text
    assert "suggested_issue_template: hardware-support" in text
    assert "Attach the support bundle." in text
    assert "Optional deeper-evidence commands:" in text
    assert "lsusb -v -d 048d:7001" in text


def test_format_device_discovery_text_includes_sysfs_aux_candidate_details() -> None:
    text = format_device_discovery_text(
        {
            "selected_backend": "sysfs-leds",
            "usb_ids": [],
            "summary": {"candidate_count": 1, "supported_count": 1, "attention_count": 0},
            "support_actions": {},
            "candidates": [
                {
                    "usb_vid": "",
                    "usb_pid": "",
                    "product": "usbmouse::rgb",
                    "device_type": "mouse",
                    "status": "supported",
                    "recommended_action": "Use the Mouse device context from the tray.",
                    "probe_names": ["sysfs-mouse"],
                    "sysfs_led": "usbmouse::rgb",
                    "sysfs_led_dir": "/sys/class/leds/usbmouse::rgb",
                }
            ],
        }
    )

    assert "sysfs usbmouse::rgb type=mouse status=supported" in text
    assert "probes: sysfs-mouse" in text
    assert "sysfs_led: usbmouse::rgb" in text
    assert "sysfs_led_dir: /sys/class/leds/usbmouse::rgb" in text


def test_collect_device_discovery_marks_supported_experimental_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": "ite8233",
            "probes": [
                {
                    "name": "ite8233",
                    "available": True,
                    "stability": "experimental",
                    "selection_enabled": True,
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x7001"},
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:7001"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0x7001",
                "product": "ITE Device(8233)",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.hidraw_devices_snapshot", lambda: [])

    payload = collect_device_discovery(include_usb=True)

    assert payload["candidates"][0]["status"] == "supported"
    assert payload["support_actions"]["recommended_issue_template"] == "experimental-backend-confirmation"


def test_collect_device_discovery_includes_sysfs_mouse_aux_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": "sysfs-leds",
            "probes": [
                {
                    "name": "sysfs-mouse",
                    "available": True,
                    "stability": "experimental",
                    "selection_enabled": True,
                    "identifiers": {
                        "device_type": "mouse",
                        "context_key": "mouse:sysfs:usbmouse__rgb",
                        "led": "usbmouse::rgb",
                        "led_dir": "/sys/class/leds/usbmouse::rgb",
                    },
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: [])
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_devices_snapshot", lambda targets: [])
    monkeypatch.setattr("src.core.diagnostics.device_discovery.hidraw_devices_snapshot", lambda: [])

    payload = collect_device_discovery(include_usb=True)

    assert payload["summary"]["candidate_count"] == 1
    assert payload["candidates"][0]["device_type"] == "mouse"
    assert payload["candidates"][0]["context_key"] == "mouse:sysfs:usbmouse__rgb"
    assert payload["candidates"][0]["probe_names"] == ["sysfs-mouse"]


def test_collect_device_discovery_recommends_bug_report_for_supported_validated_backend(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": "sysfs-leds",
            "probes": [
                {
                    "name": "sysfs-leds",
                    "available": True,
                    "stability": "validated",
                    "selection_enabled": True,
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x600b"},
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:600b"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0x600b",
                "product": "RGB Keyboard",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.hidraw_devices_snapshot", lambda: [])

    payload = collect_device_discovery(include_usb=True)

    assert payload["support_actions"]["recommended_issue_template"] == "bug-report"
    assert payload["candidates"][0]["device_type"] == "keyboard"


def test_collect_device_discovery_marks_ite8258_candidate_as_keyboard(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": None,
            "probes": [
                {
                    "name": "ite8258",
                    "available": False,
                    "stability": "experimental",
                    "selection_enabled": False,
                    "selection_reason": "experimental backend disabled",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0xc195"},
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:c195"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0xc195",
                "product": "ITE Device(8258)",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.hidraw_devices_snapshot",
        lambda: [{"vendor_id": "0x048d", "product_id": "0xc195", "devnode": "/dev/hidraw7"}],
    )

    payload = collect_device_discovery(include_usb=True)

    assert payload["candidates"][0]["status"] == "experimental_disabled"
    assert payload["candidates"][0]["device_type"] == "keyboard"
    assert payload["candidates"][0]["probe_names"] == ["ite8258"]


def test_collect_device_discovery_marks_ite8295_zones_candidate_as_keyboard(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.backend_probe_snapshot",
        lambda: {
            "selected": None,
            "probes": [
                {
                    "name": "ite8295-zones",
                    "available": False,
                    "stability": "experimental",
                    "selection_enabled": False,
                    "selection_reason": "experimental backend disabled",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0xc963"},
                }
            ],
        },
    )
    monkeypatch.setattr("src.core.diagnostics.device_discovery.usb_ids_snapshot", lambda *, include_usb: ["048d:c963"])
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.usb_devices_snapshot",
        lambda targets: [
            {
                "idVendor": "0x048d",
                "idProduct": "0xc963",
                "product": "ITE Device(8295)",
                "manufacturer": "ITE Tech. Inc.",
            }
        ],
    )
    monkeypatch.setattr(
        "src.core.diagnostics.device_discovery.hidraw_devices_snapshot",
        lambda: [{"vendor_id": "0x048d", "product_id": "0xc963", "devnode": "/dev/hidraw9"}],
    )

    payload = collect_device_discovery(include_usb=True)

    assert payload["candidates"][0]["status"] == "experimental_disabled"
    assert payload["candidates"][0]["device_type"] == "keyboard"
    assert payload["candidates"][0]["probe_names"] == ["ite8295-zones"]
