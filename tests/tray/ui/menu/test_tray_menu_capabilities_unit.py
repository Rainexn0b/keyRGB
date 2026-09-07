from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import ClassVar

import pytest

from keyrgb.tray.ui import menu as tray_menu


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = list(items)


class FakePystray:
    Menu = FakeMenu


def fake_item(text, _action, **kwargs):
    return {
        "text": str(text),
        "enabled": kwargs.get("enabled", True),
        "action": _action,
        "checked": kwargs.get("checked"),
        "default": kwargs.get("default", False),
    }


@dataclass
class DummyCaps:
    per_key: bool
    hardware_effects: bool
    brightness: bool = True
    color: bool = True
    palette: bool = False


class DummyConfig:
    effect = "none"
    speed = 5
    brightness = 25
    lightbar_brightness = 25
    color = (255, 0, 0)
    tray_device_context = "keyboard"
    software_effect_target = "keyboard"

    def reload(self):
        return


class DummyEngine:
    device_available = True

    def _ensure_device_available(self):
        return True


class DummyTray:
    def __init__(self, caps: DummyCaps):
        self.backend_caps = caps
        self.config = DummyConfig()
        self.engine = DummyEngine()
        self.is_off = False
        self.backend = None
        self.backend_probe = None
        self.device_discovery = None
        self.system_power_status = None
        self.effective_secondary_routes = ()
        self.selected_device_context = "keyboard"

    # Callbacks referenced by menu builder
    def _on_effect_clicked(self, *_a, **_k):
        return

    def _on_speed_clicked(self, *_a, **_k):
        return

    def _on_brightness_clicked(self, *_a, **_k):
        return

    def _on_device_context_clicked(self, *_a, **_k):
        return

    def _on_selected_device_color_clicked(self, *_a, **_k):
        return

    def _on_selected_device_brightness_clicked(self, *_a, **_k):
        return

    def _on_selected_device_turn_off_clicked(self, *_a, **_k):
        return

    def _on_selected_device_turn_on_clicked(self, *_a, **_k):
        return

    def _on_software_effect_target_clicked(self, *_a, **_k):
        return

    def _on_power_settings_clicked(self, *_a, **_k):
        return

    def _on_power_mode_settings_clicked(self, *_a, **_k):
        return

    def _on_support_debug_clicked(self, *_a, **_k):
        return

    def _on_backend_discovery_clicked(self, *_a, **_k):
        return

    def _on_perkey_clicked(self, *_a, **_k):
        return

    def _on_tuxedo_gui_clicked(self, *_a, **_k):
        return

    def _on_hardware_color_clicked(self, *_a, **_k):
        return

    def _on_hardware_static_mode_clicked(self, *_a, **_k):
        return

    def _on_reactive_color_clicked(self, *_a, **_k):
        return

    def _on_off_clicked(self, *_a, **_k):
        return

    def _on_turn_on_clicked(self, *_a, **_k):
        return

    def _on_quit_clicked(self, *_a, **_k):
        return

    def _log_exception(self, *_a, **_k):
        return


def test_menu_uses_detected_backend_hardware_effects_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyBackend:
        def capabilities(self):
            return DummyCaps(per_key=True, hardware_effects=True)

        def effects(self):
            return {"rainbow": object(), "breathing": object(), "wave": object()}

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.backend = DummyBackend()

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Effects (3 modes)" in labels


def test_menu_hides_items_when_capabilities_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Effects" not in labels
    assert "Software Color Editor" not in labels
    assert "Support Tools…" not in labels
    assert "Settings" in labels
    assert "Debug" not in labels
    assert "Open Debug Tools…" not in labels
    assert "Detect New Backends" not in labels
    assert "Open Backend Discovery…" not in labels


def test_menu_keeps_lighting_editor_for_uniform_keyboard_with_secondary_device() -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.effective_secondary_routes = (
        SimpleNamespace(available=True, route=SimpleNamespace(supports_profile_state=True)),
    )
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "supported",
                "probe_names": ["ite8233_none_chassis_lightbar_clevo"],
            }
        ]
    }
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [item["text"] for item in items if isinstance(item, dict)]

    assert "Lighting Profiles" in labels


def test_menu_hides_uniform_color_picker_when_color_capability_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False, color=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Static Mode" in labels
    assert "Hardware Uniform Color…" not in labels
    assert not any(label.startswith("Hardware Effects") for label in labels)


def test_menu_marks_brightness_unsupported_when_capability_metadata_is_missing() -> None:
    tray = DummyTray(None)  # type: ignore[arg-type]

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    brightness = next(item for item in items if isinstance(item, dict) and item["text"].startswith("Brightness"))

    assert brightness["text"] == "Brightness Override (not supported)"
    assert brightness["enabled"] is False


def test_menu_hides_hardware_color_and_effect_rows_in_software_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True, color=True))
    tray.config.effect = "reactive_ripple"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    hardware_items = [i for i in items if isinstance(i, dict)]

    assert next(i for i in hardware_items if i["text"] == "Hardware Static Mode")
    assert not any(i["text"] == "Hardware Uniform Color…" for i in hardware_items)
    assert not any(i["text"].startswith("Hardware Effects") for i in hardware_items)


def test_hardware_static_row_checked_state_represents_hardware_mode_not_only_static_effect() -> None:
    checked = tray_menu.menu_callbacks.checked_hw_static(
        type("Tray", (), {"is_off": False, "config": DummyConfig()})(), hw_mode=True
    )

    assert checked(object()) is True


def test_menu_includes_keyboard_status_header(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    # The first entry selects the keyboard live-control context.
    assert isinstance(items[0], dict)
    assert "Keyboard" in items[0]["text"]
    assert items[0]["enabled"] is True
    assert items[0]["checked"](object()) is True


def test_keyboard_status_formats_usb_vid_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyBackend:
        name = "ite8291r3_perkey"

    class DummyProbe:
        identifiers: ClassVar[dict[str, str]] = {"usb_vid": "0x048d", "usb_pid": "0x600b"}

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.backend = DummyBackend()
    tray.backend_probe = DummyProbe()

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "048d:600b" in items[0]["text"].lower()
