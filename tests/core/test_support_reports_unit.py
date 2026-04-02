from __future__ import annotations

import os
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.diagnostics.support_reports import build_issue_report_with_evidence, build_support_bundle_payload


def test_build_issue_report_prefers_hardware_support_for_attention_candidates() -> None:
    diagnostics = {
        "app": {"version": "0.19.1", "version_source": "pyproject"},
        "backends": {
            "selected": None,
            "selection": {"experimental_backends_enabled": False},
            "probes": [],
        },
        "system": {"kernel_release": "6.9.0", "os_release": {"PRETTY_NAME": "Fedora Linux"}},
        "env": {"XDG_CURRENT_DESKTOP": "KDE"},
        "usb_ids": ["048d:7001"],
        "dmi": {"sys_vendor": "Wootbook", "product_name": "Ultra X16"},
    }
    discovery = {
        "selected_backend": None,
        "summary": {"candidate_count": 1, "supported_count": 0, "attention_count": 1},
        "support_actions": {
            "recommended_issue_template": "hardware-support",
            "optional_capture_commands": [
                "lsusb -v -d 048d:7001",
                "sudo usbhid-dump -d 048d:7001 -e descriptor",
            ],
        },
        "candidates": [
            {
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "manufacturer": "ITE Tech. Inc.",
                "product": "ITE Device(8233)",
                "status": "known_dormant",
                "hidraw_descriptor_sizes": [64],
            }
        ],
    }

    report = build_issue_report_with_evidence(
        diagnostics=diagnostics,
        discovery=discovery,
        supplemental_evidence={
            "captures": {
                "lsusb_verbose": {
                    "command": ["lsusb", "-v", "-d", "048d:7001"],
                    "ok": True,
                    "stdout": "descriptor output",
                    "via": "direct",
                }
            },
            "backend_probes": {
                "ite8910_speed": {
                    "backend": "ite8910",
                    "effect_name": "spectrum_cycle",
                    "samples": [{"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"}],
                    "observation": {"distinct_steps": False, "notes": "1 and 3 looked nearly identical"},
                }
            },
            "manual": [{"label": "Windows OEM traffic capture"}],
        },
    )

    assert report["template"] == "hardware-support"
    assert report["title"] == "Hardware support: Wootbook Ultra X16 (0x048d:0x7001)"
    assert "what_happened" in report["fields"]
    assert "048d:7001" in report["fields"]["lsusb"]
    assert "extra_capture_commands" in report["fields"]
    assert "usbhid-dump" in report["fields"]["extra_capture_commands"]
    assert "additional_evidence" in report["fields"]
    assert "descriptor output" in report["fields"]["additional_evidence"]
    assert "Guided backend probes:" in report["fields"]["additional_evidence"]
    assert "1 and 3 looked nearly identical" in report["fields"]["additional_evidence"]
    assert "Template: Hardware support / diagnostics" in report["markdown"]


def test_build_issue_report_uses_experimental_confirmation_for_selected_experimental_backend() -> None:
    diagnostics = {
        "app": {"version": "0.19.1", "version_source": "pyproject"},
        "backends": {
            "selected": "ite8297",
            "selection": {"experimental_backends_enabled": True},
            "probes": [{"name": "ite8297", "stability": "experimental"}],
        },
        "system": {"kernel_release": "6.9.0", "os_release": {"PRETTY_NAME": "Nobara 41"}},
        "env": {"DESKTOP_SESSION": "plasma"},
        "dmi": {"sys_vendor": "Tongfang", "product_name": "GM7PX0N"},
    }
    discovery = {
        "selected_backend": "ite8297",
        "summary": {"candidate_count": 1, "supported_count": 1, "attention_count": 0},
        "support_actions": {"recommended_issue_template": "experimental-backend-confirmation"},
        "candidates": [
            {
                "usb_vid": "0x048d",
                "usb_pid": "0x8297",
                "manufacturer": "ITE Tech. Inc.",
                "product": "ITE RGB Controller",
                "status": "supported",
            }
        ],
    }

    report = build_issue_report_with_evidence(diagnostics=diagnostics, discovery=discovery, supplemental_evidence=None)

    assert report["template"] == "experimental-backend-confirmation"
    assert report["fields"]["backend"] == "ite8297"
    assert report["fields"]["usb_id"] == "0x048d:0x8297"
    assert "Selected backend shown by KeyRGB: ite8297" in report["fields"]["confirmation"]


def test_build_support_bundle_payload_embeds_issue_report() -> None:
    payload = build_support_bundle_payload(
        diagnostics={"app": {}},
        discovery={"summary": {}},
        supplemental_evidence={"captures": {}},
    )

    assert payload["diagnostics"] == {"app": {}}
    assert payload["device_discovery"] == {"summary": {}}
    assert payload["supplemental_evidence"] == {"captures": {}}
    assert payload["issue_report"]["template"] == "hardware-support"