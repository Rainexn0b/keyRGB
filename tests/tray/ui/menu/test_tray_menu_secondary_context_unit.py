from __future__ import annotations

from dataclasses import dataclass

import pytest

from keyrgb.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)
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


def test_menu_shows_secondary_status_as_context_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray._on_device_context_clicked = lambda context_key: setattr(tray, "selected_device_context", context_key)
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "product": "ITE Device(8233)",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "experimental_disabled",
            }
        ]
    }

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert "Keyboard" in items[0]["text"]
    assert "Connected:" not in [item["text"] for item in items if isinstance(item, dict)]
    assert "048d:7001" in items[1]["text"].lower()
    assert items[1]["enabled"] is True
    items[1]["action"](object(), object())
    assert tray.selected_device_context == "lightbar:048d:7001"


def test_menu_uses_capability_filtered_body_when_lightbar_context_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "product": "ITE Device(8233)",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "experimental_disabled",
            }
        ]
    }
    tray.selected_device_context = "lightbar:048d:7001"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Static Color…" in labels
    assert "Software Effects" in labels
    assert "Lightbar backend is present but disabled by experimental-backend policy" not in labels
    assert "Support Tools…" not in labels
    assert "Settings" in labels
    assert "Quit" in labels


def test_menu_exposes_lightbar_controls_alongside_profile_editor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "product": "ITE Device(8233)",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "supported",
            }
        ]
    }
    tray.secondary_device_controls = {"lightbar:048d:7001": True}
    tray.selected_device_context = "lightbar:048d:7001"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Static Color…" in labels
    assert "Brightness Override" in labels
    assert "Lighting Profiles" in labels
    assert "Turn Off" in labels
    assert "Support Tools…" not in labels
    assert "Settings" in labels
    assert "Quit" in labels


def test_shared_secondary_context_explains_that_brightness_follows_keyboard(monkeypatch) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.selected_device_context = "logo:simulated"
    entry = {
        "key": "logo:simulated",
        "device_type": "logo",
        "text": "Logo (simulated)",
    }
    route = SecondaryDeviceRoute(
        device_type="logo",
        backend_name="ite8258-chassis-logo",
        display_name="Logo",
        state_key="logo",
        get_backend=lambda: object(),
        get_device=lambda: object(),
        supports_uniform_color=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
    )
    monkeypatch.setattr(tray_menu.menu_status, "device_context_entries", lambda _tray: [entry])
    monkeypatch.setattr(tray_menu, "route_for_context_entry", lambda _entry: route)
    monkeypatch.setattr(tray_menu.menu_status, "device_context_controls_available", lambda *_args: True)

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    brightness = next(
        item for item in items if isinstance(item, dict) and item["text"].startswith("Brightness Override")
    )

    assert brightness["text"] == "Brightness Override (follows Keyboard)"
    assert brightness["enabled"] is False


def test_independent_secondary_context_off_state_offers_turn_on(monkeypatch) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.selected_device_context = "lightbar:simulated"
    tray.config.lightbar_brightness = 0
    entry = {
        "key": "lightbar:simulated",
        "device_type": "lightbar",
        "text": "Lightbar (simulated)",
    }
    route = SecondaryDeviceRoute(
        device_type="lightbar",
        backend_name="ite8233_none_chassis_lightbar_clevo",
        display_name="Lightbar",
        state_key="lightbar",
        get_backend=lambda: object(),
        get_device=lambda: object(),
        config_brightness_attr="lightbar_brightness",
        supports_uniform_color=True,
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
    )
    monkeypatch.setattr(tray_menu.menu_status, "device_context_entries", lambda _tray: [entry])
    monkeypatch.setattr(tray_menu, "route_for_context_entry", lambda _entry: route)
    monkeypatch.setattr(tray_menu.menu_status, "device_context_controls_available", lambda *_args: True)

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    hardware_labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Turn On Lightbar" in hardware_labels


def test_software_effects_include_enabled_lighting_areas_toggle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "product": "ITE Device(8233)",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "supported",
            }
        ]
    }
    tray.secondary_device_controls = {"lightbar:048d:7001": True}

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    submenu = next(i["action"] for i in items if isinstance(i, dict) and i["text"] == "Software Effects")
    labels = [i["text"] for i in submenu.items if isinstance(i, dict)]
    toggle = next(i for i in submenu.items if isinstance(i, dict) and i["text"] == "Include enabled lighting areas")

    assert "Include enabled lighting areas" in labels
    assert not any(i.get("text") == "Effect output" for i in items if isinstance(i, dict))
    assert toggle["checked"](object()) is False
    tray.config.software_effect_target = "all_uniform_capable"
    assert toggle["checked"](object()) is True


def test_software_effects_toggle_stays_visible_when_all_profile_areas_are_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "supported",
            }
        ]
    }
    tray.secondary_device_controls = {"lightbar:048d:7001": True}
    tray._active_secondary_lighting = {"areas": {"lightbar": {"enabled": False}}}

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    submenu = next(i["action"] for i in items if isinstance(i, dict) and i["text"] == "Software Effects")

    assert any(isinstance(i, dict) and i["text"] == "Include enabled lighting areas" for i in submenu.items)


def test_software_target_toggle_uses_pystray_compatible_arity_and_flips_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))
    tray.device_discovery = {
        "candidates": [
            {
                "device_type": "lightbar",
                "product": "ITE Device(8233)",
                "usb_vid": "0x048d",
                "usb_pid": "0x7001",
                "status": "supported",
            }
        ]
    }
    tray.secondary_device_controls = {"lightbar:048d:7001": True}

    selected: list[str] = []
    tray._on_software_effect_target_clicked = selected.append
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    submenu = next(i["action"] for i in items if isinstance(i, dict) and i["text"] == "Software Effects")
    toggle_action = next(
        i["action"] for i in submenu.items if isinstance(i, dict) and i["text"] == "Include enabled lighting areas"
    )

    assert toggle_action.__code__.co_argcount == 2
    toggle_action(object(), object())
    assert selected == ["all_uniform_capable"]

    tray.config.software_effect_target = "all_uniform_capable"
    toggle_action(object(), object())
    assert selected == ["all_uniform_capable", "keyboard"]


def test_menu_renders_invalid_selected_context_fallback_without_mutating_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.selected_device_context = "missing:device"
    tray.config.tray_device_context = "missing:device"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert tray.selected_device_context == "missing:device"
    assert tray.config.tray_device_context == "missing:device"
    assert "Keyboard" in items[0]["text"]
