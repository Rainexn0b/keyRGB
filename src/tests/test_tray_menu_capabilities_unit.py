from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.tray import menu as tray_menu


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

    assert "🎨 Hardware Effects" not in labels
    assert "🎹 Per-Key Colors" not in labels
