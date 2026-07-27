"""Direct unit coverage for diagnostics support report-text helpers."""

from __future__ import annotations

from src.core.diagnostics.support import _report_text as rt


def test_join_and_selected_backend_helpers() -> None:
    assert rt.join_non_empty_sections("", "a", "", "b") == "a\n\nb"
    assert rt.selected_backend_probe(None) is None
    assert rt.selected_backend_probe({"backends": "x"}) is None
    assert rt.selected_backend_probe({"backends": {"selected": "", "probes": []}}) is None
    assert rt.selected_backend_probe(
        {"backends": {"selected": "sysfs", "probes": [{"name": "other"}, {"name": "sysfs", "ok": True}]}}
    ) == {"name": "sysfs", "ok": True}
    assert rt.selected_backend_probe({"backends": {"selected": "sysfs", "probes": [{"name": "x"}]}}) is None

    assert rt.selected_backend_name({"selected_backend": "a"}, None) == ""  # wrong shape first arg
    assert rt.selected_backend_name(None, {"selected_backend": "disc"}) == "disc"
    assert rt.selected_backend_name({"backends": {"selected": "diag"}}, {"selected_backend": ""}) == "diag"
    assert rt.selected_backend_name(None, None) == ""


def test_primary_candidate_and_labels() -> None:
    assert rt.primary_candidate(None) is None
    assert rt.primary_candidate({"candidates": "x"}) is None
    disc = {
        "candidates": [
            {"status": "supported", "product": "A"},
            {"status": "known_dormant", "product": "B", "usb_vid": "048d", "usb_pid": "ce00"},
        ]
    }
    primary = rt.primary_candidate(disc)
    assert primary is not None and primary["product"] == "B"
    assert "B" in rt.candidate_label(primary)
    assert "048d:ce00" in rt.candidate_label(primary)
    assert rt.candidate_label(None) == ""

    assert rt.hardware_label({"dmi": {"sys_vendor": "XMG", "product_name": "Neo"}}, None) == "XMG Neo"
    assert rt.hardware_label({"dmi": {"product_name": "Only"}}, None) == "Only"
    assert "B" in rt.hardware_label(None, disc)
    assert rt.hardware_label(None, None) == "<brand/model>"

    assert rt.primary_usb_id(disc, None) == "048d:ce00"
    assert rt.primary_usb_id(None, {"usb_ids": ["1111:2222"]}) == "1111:2222"
    assert rt.primary_usb_id(None, None) == ""

    assert "048d" in rt.usb_ids_text({"usb_ids": ["048d:ce00", "048d:ce00"]}, None)
    assert rt.usb_ids_text(None, {"usb_ids": ["abcd:ef01"]}) == "abcd:ef01"


def test_experimental_environment_version_and_discovery_text() -> None:
    assert rt.experimental_enabled_text(None) == "unknown"
    assert rt.experimental_enabled_text({"backends": {}}) == "unknown"
    assert (
        rt.experimental_enabled_text({"backends": {"selection": {"experimental_backends_enabled": True}}}) == "enabled"
    )
    assert (
        rt.experimental_enabled_text({"backends": {"selection": {"experimental_backends_enabled": False}}})
        == "disabled"
    )
    assert rt.experimental_enabled_text({"backends": {"selection": {}}}) == "unknown"

    env = rt.environment_text(None)
    assert "Distro:" in env
    full = rt.environment_text(
        {
            "system": {"os_release": {"PRETTY_NAME": "Fedora"}, "kernel_release": "6.x"},
            "env": {"XDG_CURRENT_DESKTOP": "KDE"},
            "app": {"version": "1.0", "version_source": "git", "dist_version": "0.9"},
        }
    )
    assert "Fedora" in full and "KDE" in full and "1.0" in full

    assert rt.version_text(None) == "unknown"
    assert rt.version_text({"app": {}}) == "unknown"
    assert rt.version_text({"app": {"version": "2.0", "version_source": "rpm"}}) == "2.0 (rpm)"
    assert rt.version_text({"app": {"version": "2.0"}}) == "2.0"

    assert rt.discovery_summary_text(None) == ""
    summary = rt.discovery_summary_text(
        {
            "summary": {"candidate_count": 2, "supported_count": 1, "attention_count": 1},
            "candidates": [{"status": "known_dormant", "product": "KB", "hidraw_descriptor_sizes": [64, 128]}],
            "support_actions": {"next_steps": ["install udev rules"]},
        }
    )
    assert "candidates=2" in summary
    assert "HID report descriptor sizes" in summary
    assert "install udev rules" in summary

    assert rt.optional_capture_commands_text(None) == ""
    cmds = rt.optional_capture_commands_text(
        {"support_actions": {"optional_capture_commands": ["lsusb", ""]}},
        prefix="Capture:",
    )
    assert cmds.startswith("Capture:")
    assert "- lsusb" in cmds


def test_supplemental_evidence_and_json_text() -> None:
    assert rt.supplemental_evidence_text(None) == ""
    assert rt.supplemental_evidence_text({}) == ""

    text = rt.supplemental_evidence_text(
        {
            "captures": {
                "lsusb": {
                    "command": ["lsusb"],
                    "via": "shell",
                    "returncode": 0,
                    "stdout": "Bus 001",
                    "stderr": "warn",
                    "error": "",
                },
                "bad": "skip",
            },
            "backend_probes": {
                "ite8291r3_speed": {
                    "backend": "ite8291r3_perkey",
                    "effect_name": "wave",
                    "selection_effect_name": "wave",
                    "started_at": "t0",
                    "completed_at": "t1",
                    "samples": [
                        {"ui_speed": 1, "payload_speed": 10, "raw_speed_hex": "0x0a"},
                        "skip",
                    ],
                    "observation": {"distinct_steps": True, "notes": "looks good"},
                },
                "bad": 1,
            },
            "manual": [{"label": "Photo of keyboard"}, "x"],
        },
        prefix="Evidence:",
    )
    assert text.startswith("Evidence:")
    assert "Bus 001" in text
    assert "stderr:" in text
    assert "Guided backend probes:" in text
    assert "ui=1" in text
    assert "notes: looks good" in text
    assert "Photo of keyboard" in text

    assert rt.json_text(None) == "{}"
    assert '"a"' in rt.json_text({"b": 1, "a": 2})
