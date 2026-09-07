from __future__ import annotations

from dataclasses import dataclass
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


def test_menu_groups_controls_in_the_agreed_order() -> None:
    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=True))

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [entry["text"] for entry in items if isinstance(entry, dict)]

    expected = [
        "Brightness Override",
        "Lighting Profiles",
        "Hardware Static Mode",
        "Software Effects",
        "Effect Speed",
        "Settings",
        "Turn Off",
        "Quit",
    ]
    positions = [labels.index(label) for label in expected]
    assert positions == sorted(positions)


def test_keyboard_status_badges_research_backed_experimental_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyBackend:
        name = "ite8910_perkey"
        stability = "experimental"
        experimental_evidence = "reverse_engineered"

    class DummyProbe:
        identifiers: ClassVar[dict[str, str]] = {"usb_vid": "0x048d", "usb_pid": "0x8910"}

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.backend = DummyBackend()
    tray.backend_probe = DummyProbe()

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    text = items[0]["text"].lower()

    assert "ite 8910" in text
    assert "experimental" in text
    assert "research-backed" in text


def test_keyboard_status_shows_warning_when_not_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.engine.device_available = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "not detected" in items[0]["text"].lower()


def test_menu_includes_active_mode_indicator_between_off_and_quit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.config.effect = "none"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert items[-3]["text"].lower().startswith("turn ")
    assert items[-2]["enabled"] is False
    assert "mode:" in items[-2]["text"].lower()
    assert items[-1]["text"] == "Quit"


def test_tray_active_indicator_shows_perkey_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.profile import profiles as core_profiles

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


def test_tray_active_indicator_falls_back_to_unknown_when_profile_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))
    tray.config.effect = "perkey"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    mode_text = items[-2]["text"].lower()

    assert "mode:" in mode_text
    assert "software" in mode_text
    assert "unknown" in mode_text


def test_system_power_mode_menu_returns_none_when_status_snapshot_is_missing() -> None:
    from keyrgb.tray.ui import menu_sections

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))

    assert (
        menu_sections.build_system_power_mode_menu(
            tray,
            pystray=FakePystray,
            item=fake_item,
        )
        is None
    )


def test_menu_includes_system_power_item_when_builder_returns_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tray_menu.menu_sections,
        "build_system_power_mode_menu",
        lambda *args, **kwargs: fake_item("Power Mode", lambda *_a, **_k: None),
    )

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Power Mode" in labels


def test_system_power_menu_contains_power_mode_settings_entry() -> None:
    from keyrgb.tray.ui import menu_sections

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.system_power_status = type(
        "Status",
        (),
        {"supported": True, "identifiers": {"can_apply": "true"}, "mode": None},
    )()
    power_menu = menu_sections.build_system_power_mode_menu(tray, pystray=FakePystray, item=fake_item)

    assert isinstance(power_menu, FakeMenu)
    labels = [entry["text"] for entry in power_menu.items if isinstance(entry, dict)]
    assert labels[-1] == "Power Mode Settings…"


def test_perkey_profiles_menu_falls_back_to_editor_when_profile_listing_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from keyrgb.core.profile import profiles as core_profiles
    from keyrgb.tray.ui import menu_sections

    monkeypatch.setattr(core_profiles, "list_profiles", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))

    menu = menu_sections.build_perkey_profiles_menu(
        tray,
        pystray=FakePystray,
        item=fake_item,
        per_key_supported=True,
    )

    assert isinstance(menu, FakeMenu)
    assert [entry["text"] for entry in menu.items if isinstance(entry, dict)] == ["Lighting Profile Editor"]
