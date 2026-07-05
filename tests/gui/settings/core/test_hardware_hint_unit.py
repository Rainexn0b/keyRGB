from __future__ import annotations

from src.gui.settings.hardware_hint import extract_unsupported_rgb_controllers_hint


def test_hardware_hint_reports_experimental_ite8910_toggle_path() -> None:
    text = extract_unsupported_rgb_controllers_hint(
        {
            "probes": [
                {
                    "name": "ite8910_perkey",
                    "reason": "experimental backend disabled (detected 0x048d:0x8910; enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
                    "experimental_evidence": "reverse_engineered",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8910"},
                }
            ]
        }
    )

    assert "experimental" in text.lower()
    assert "research-backed" in text.lower()
    assert "ite8910_perkey" in text


def test_hardware_hint_reports_unsupported_fusion2_path() -> None:
    text = extract_unsupported_rgb_controllers_hint(
        {
            "probes": [
                {
                    "name": "ite8291r3_perkey",
                    "reason": "usb device present but unsupported by ite8291r3_perkey backend (0x048d:0x8297)",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8297"},
                }
            ]
        }
    )

    assert "tier 3" in text.lower()
    assert "0x048d:0x8297" in text.lower()


def test_hardware_hint_prefers_experimental_backend_path_for_ite8297() -> None:
    text = extract_unsupported_rgb_controllers_hint(
        {
            "probes": [
                {
                    "name": "ite8291r3_perkey",
                    "reason": "usb device present but unsupported by ite8291r3_perkey backend (0x048d:0x8297)",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8297"},
                },
                {
                    "name": "ite8297_uniform",
                    "stability": "experimental",
                    "reason": "experimental backend disabled (detected 0x048d:0x8297; enable Experimental backends in Settings or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)",
                    "experimental_evidence": "reverse_engineered",
                    "identifiers": {"usb_vid": "0x048d", "usb_pid": "0x8297"},
                },
            ]
        }
    )

    assert "research-backed" in text.lower()
    assert "ite8297_uniform" in text
    assert "tier 3" not in text.lower()
