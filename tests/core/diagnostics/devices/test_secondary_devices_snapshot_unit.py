from __future__ import annotations

from types import SimpleNamespace

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.diagnostics import secondary_devices


class _StubConfig:
    def __init__(self) -> None:
        self.tray_device_context = "keyboard"
        self.software_effect_target = "keyboard"
        self.brightness = 40

    def get_secondary_device_brightness(self, state_key, *, fallback_keys=(), default=0):
        return 40

    def get_secondary_device_color(self, state_key, *, fallback_keys=(), default=(255, 0, 0)):
        return (1, 2, 3)

    def get_secondary_device_enabled(self, state_key, *, fallback_keys=(), default=False):
        return True


def _patch_config(monkeypatch, config) -> None:
    monkeypatch.setattr(secondary_devices, "_load_config", lambda: config)


def _patch_parent_probe(monkeypatch, *, available: bool, reason: str) -> None:
    from src.core.backends.ite8258_perkey_chassis.backend import Ite8258ChassisBackend

    monkeypatch.setattr(
        Ite8258ChassisBackend,
        "probe",
        lambda self: SimpleNamespace(available=available, reason=reason),
    )


def test_zones_available_when_parent_probe_succeeds(monkeypatch) -> None:
    _patch_config(monkeypatch, _StubConfig())
    _patch_parent_probe(monkeypatch, available=True, reason="hidraw device present (/dev/hidraw3)")
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    snap = secondary_devices.secondary_devices_snapshot([])

    assert snap["experimental_backends_enabled"] is True
    assert [route["device_type"] for route in snap["virtual_routes"]] == ["logo", "neon", "vent"]
    assert all(route["parent_available"] for route in snap["virtual_routes"])

    assert [context["device_type"] for context in snap["expected_tray_contexts"]] == [
        "keyboard",
        "logo",
        "neon",
        "vent",
    ]
    editor_keys = [row["state_key"] for row in snap["expected_profile_editor_rows"]]
    assert "ite8258_chassis_logo" in editor_keys
    assert "ite8258_chassis_neon" in editor_keys
    assert "ite8258_chassis_vent" in editor_keys
    assert snap["software_effect_target"]["all_compatible_devices_enabled"] is True

    # Persisted state is reported for every registered secondary route.
    assert set(snap["secondary_device_state"]) == {
        "lightbar",
        "mouse",
        "ite8258_chassis_logo",
        "ite8258_chassis_neon",
        "ite8258_chassis_vent",
    }
    assert snap["secondary_device_state"]["ite8258_chassis_logo"] == {
        "enabled": True,
        "brightness": 40,
        "color": [1, 2, 3],
    }


def test_zones_absent_when_parent_probe_fails(monkeypatch) -> None:
    _patch_config(monkeypatch, _StubConfig())
    _patch_parent_probe(monkeypatch, available=False, reason="no matching hidraw device")

    snap = secondary_devices.secondary_devices_snapshot([])

    assert not any(route["parent_available"] for route in snap["virtual_routes"])
    assert all(route["parent_reason"] == "no matching hidraw device" for route in snap["virtual_routes"])

    # Only the keyboard context renders; software target stays keyboard-only.
    assert [context["device_type"] for context in snap["expected_tray_contexts"]] == ["keyboard"]
    assert snap["software_effect_target"]["all_compatible_devices_enabled"] is False


def test_simulation_snapshot_reports_all_routes_without_hardware(monkeypatch) -> None:
    _patch_config(monkeypatch, _StubConfig())
    monkeypatch.setenv("KEYRGB_SIMULATE_SECONDARY_DEVICES", "1")

    snap = secondary_devices.secondary_devices_snapshot([])

    assert [route["device_type"] for route in snap["effective_routes"]] == [
        "lightbar",
        "mouse",
        "logo",
        "neon",
        "vent",
    ]
    assert all(route["available"] for route in snap["effective_routes"])
    assert all(route["simulated"] for route in snap["effective_routes"])
    assert {route["availability_source"] for route in snap["effective_routes"]} == {"simulation"}
    assert [context["device_type"] for context in snap["expected_tray_contexts"]] == [
        "keyboard",
        "lightbar",
        "mouse",
        "logo",
        "neon",
        "vent",
    ]
    assert len(snap["expected_profile_editor_rows"]) == 5
    assert all(row["simulated"] for row in snap["expected_profile_editor_rows"])


def test_auxiliary_candidate_controls_follow_status(monkeypatch) -> None:
    _patch_config(monkeypatch, _StubConfig())
    _patch_parent_probe(monkeypatch, available=False, reason="no matching hidraw device")

    candidates = [
        {"device_type": "keyboard", "status": "supported", "usb_vid": "0x048d", "usb_pid": "0xc197"},
        {
            "device_type": "lightbar",
            "status": "supported",
            "usb_vid": "0x048d",
            "usb_pid": "0x7001",
            "product": "Lightbar",
            "context_key": "lightbar:0x048d:0x7001",
        },
        {
            "device_type": "unknown",
            "status": "unrecognized_ite",
            "usb_vid": "0x048d",
            "usb_pid": "0xc193",
            "product": "Lenovo Lighting",
            "context_key": "unknown:0x048d:0xc193",
        },
    ]

    snap = secondary_devices.secondary_devices_snapshot(candidates)

    aux = {entry["device_type"]: entry for entry in snap["auxiliary_candidates"]}
    assert set(aux) == {"lightbar", "unknown"}  # keyboard candidate is excluded
    assert aux["lightbar"]["controls_available"] is True
    assert aux["unknown"]["controls_available"] is False

    assert [context["device_type"] for context in snap["expected_tray_contexts"]] == [
        "keyboard",
        "lightbar",
        "unknown",
    ]


def test_snapshot_tolerates_missing_config(monkeypatch) -> None:
    _patch_config(monkeypatch, None)
    _patch_parent_probe(monkeypatch, available=False, reason="no matching hidraw device")

    snap = secondary_devices.secondary_devices_snapshot(None)

    assert snap["selected_device_context"] == "keyboard"
    assert snap["software_effect_target"]["current"] == "keyboard"
    assert snap["auxiliary_candidates"] == []
    assert snap["secondary_device_state"] == {}
