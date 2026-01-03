from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.tray.ui import menu as tray_menu


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = list(items)


class FakePystray:
    Menu = FakeMenu


def fake_item(text, _action, **kwargs):
    return {"text": str(text), "enabled": kwargs.get("enabled", True)}


@dataclass
class DummyCaps:
    per_key: bool
    hardware_effects: bool
    palette: bool = False


class DummyConfig:
    effect = "none"
    speed = 5
    brightness = 25
    color = (255, 0, 0)

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

    # Callbacks referenced by menu builder
    def _on_effect_clicked(self, *_a, **_k):
        return

    def _on_speed_clicked(self, *_a, **_k):
        return

    def _on_brightness_clicked(self, *_a, **_k):
        return

    def _on_power_settings_clicked(self, *_a, **_k):
        return

    def _on_perkey_clicked(self, *_a, **_k):
        return

    def _on_tuxedo_gui_clicked(self, *_a, **_k):
        return

    def _on_off_clicked(self, *_a, **_k):
        return

    def _on_turn_on_clicked(self, *_a, **_k):
        return

    def _on_quit_clicked(self, *_a, **_k):
        return

    def _on_tcc_profiles_gui_clicked(self, *_a, **_k):
        return

    def _on_tcc_profile_clicked(self, *_a, **_k):
        return

    def _log_exception(self, *_a, **_k):
        return


def test_menu_hides_items_when_capabilities_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Avoid DBus/TCC calls in the menu builder.
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Effects" not in labels
    assert "Software Color Editor" not in labels


def test_menu_includes_keyboard_status_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    # First entry should be a disabled status line.
    assert isinstance(items[0], dict)
    assert items[0]["enabled"] is False
    assert "Keyboard" in items[0]["text"]


def test_keyboard_status_formats_usb_vid_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    class DummyBackend:
        name = "ite8291r3"

    class DummyProbe:
        identifiers = {"usb_vid": "0x048d", "usb_pid": "0x600b"}

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.backend = DummyBackend()
    tray.backend_probe = DummyProbe()

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "048d:600b" in items[0]["text"].lower()


def test_keyboard_status_shows_warning_when_not_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.engine.device_available = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "not detected" in items[0]["text"].lower()


def test_menu_includes_active_mode_indicator_between_off_and_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.config.effect = "none"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert items[-3]["text"].lower().startswith("turn ")
    assert items[-2]["enabled"] is False
    assert "mode:" in items[-2]["text"].lower()
    assert items[-1]["text"] == "Quit"


def test_tray_active_indicator_shows_perkey_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: "default")

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))
    tray.config.effect = "perkey"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    # Mode indicator should show "software" and the profile name
    mode_text = items[-2]["text"].lower()
    assert "mode:" in mode_text
    assert "software" in mode_text
    assert "default" in mode_text
