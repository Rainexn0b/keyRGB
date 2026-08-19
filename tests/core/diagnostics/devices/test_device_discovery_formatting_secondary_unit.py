"""Coverage for secondary-device branches of format_device_discovery_text."""

from __future__ import annotations

from keyrgb.core.diagnostics.device_discovery_support.formatting import format_device_discovery_text


def test_format_includes_secondary_virtual_aux_and_expected_contexts() -> None:
    text = format_device_discovery_text(
        {
            "selected_backend": "ite8258_perkey_chassis",
            "summary": {"candidate_count": 1, "supported_count": 0, "attention_count": 1},
            "support_actions": {
                "recommended_issue_template": "new-device.md",
                "recommended_issue_url": "https://example.test/issue",
                "next_steps": ["enable experimental"],
                "optional_capture_commands": ["lsusb -v"],
            },
            "usb_ids": ["048d:c966"],
            "candidates": [
                "skip-me",
                {
                    "usb_vid": "048d",
                    "usb_pid": "c966",
                    "product": "Legion",
                    "device_type": "keyboard",
                    "status": "experimental_disabled",
                    "recommended_action": "opt in",
                    "probe_names": ["ite8258"],
                    "sysfs_led": "platform::kbd_backlight",
                    "sysfs_led_dir": "/sys/class/leds/x",
                    "hidraw_nodes": ["/dev/hidraw0"],
                    "hidraw_descriptor_sizes": [64],
                },
                {
                    "usb_vid": "048d",
                    "usb_pid": "ce00",
                    "product": "No sizes",
                    "device_type": "keyboard",
                    "status": "supported",
                    "hidraw_nodes": ["/dev/hidraw1"],
                },
            ],
            "secondary_devices": {
                "experimental_backends_enabled": True,
                "selected_device_context": "keyboard",
                "software_effect_target": {
                    "current": "all_uniform_capable",
                    "all_compatible_devices_enabled": True,
                },
                "virtual_routes": [
                    "skip",
                    {
                        "display_name": "Logo",
                        "backend_name": "ite8258-chassis-logo",
                        "parent_backend": "ite8258_perkey_chassis",
                        "parent_available": False,
                        "parent_reason": "parent offline",
                    },
                    {
                        "display_name": "Neon",
                        "backend_name": "ite8258-chassis-neon",
                        "parent_backend": "ite8258_perkey_chassis",
                        "parent_available": True,
                        "parent_reason": "",
                    },
                ],
                "auxiliary_candidates": [
                    "skip",
                    {
                        "usb_vid": "046d",
                        "usb_pid": "c077",
                        "product": "Mouse",
                        "device_type": "mouse",
                        "status": "supported",
                        "controls_available": True,
                    },
                ],
                "expected_tray_contexts": [
                    "skip",
                    {
                        "key": "logo",
                        "device_type": "logo",
                        "source": "virtual",
                        "controls_available": True,
                    },
                ],
            },
        }
    )

    assert "selected_backend: ite8258_perkey_chassis" in text
    assert "Recommended next steps:" in text
    assert "Optional deeper-evidence commands:" in text
    assert "USB IDs:" in text
    assert "Candidates:" in text
    assert "next: opt in" in text
    assert "hidraw_descriptor_sizes: 64" in text
    assert "hidraw_descriptor_sizes: unavailable" in text
    assert "Secondary devices:" in text
    assert "software_effect_target: all_uniform_capable" in text
    assert "virtual zone routes:" in text
    assert "parent offline" in text
    assert "auxiliary candidates:" in text
    assert "046d:c077" in text
    assert "expected tray device-context rows:" in text
    assert "key" not in text or "logo" in text
