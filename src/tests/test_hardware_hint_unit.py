from __future__ import annotations

from src.gui.settings.hardware_hint import extract_unsupported_rgb_controllers_hint


def test_hardware_hint_reports_experimental_ite8910_toggle_path() -> None:
    text = extract_unsupported_rgb_controllers_hint(
        {
            "probes": [
                {
                    "name": "ite8910",
                    "reason": "experimental backend disabled (detected 0x048d:0x8910; enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8910"},
                }
            ]
        }
    )

    assert "experimental" in text.lower()
    assert "ite8910" in text


def test_hardware_hint_reports_unsupported_fusion2_path() -> None:
    text = extract_unsupported_rgb_controllers_hint(
        {
            "probes": [
                {
                    "name": "ite8291r3",
                    "reason": "usb device present but unsupported by ite8291r3 backend (0x048d:0x8297)",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8297"},
                }
            ]
        }
    )

    assert "tier 3" in text.lower()
    assert "0x048d:0x8297" in text.lower()