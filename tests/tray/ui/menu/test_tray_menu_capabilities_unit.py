from __future__ import annotations

from dataclasses import dataclass

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.tray.ui import menu as tray_menu


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = list(items)


class FakePystray:
    Menu = FakeMenu


def fake_item(text, _action, **kwargs):
    return {"text": str(text), "enabled": kwargs.get("enabled", True), "action": _action}


@dataclass
class DummyCaps:
    per_key: bool
    hardware_effects: bool
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

    def _on_software_effect_target_clicked(self, *_a, **_k):
        return

    def _on_power_settings_clicked(self, *_a, **_k):
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

    def _on_tcc_profiles_gui_clicked(self, *_a, **_k):
        return

    def _on_tcc_profile_clicked(self, *_a, **_k):
        return

    def _log_exception(self, *_a, **_k):
        return


def test_menu_uses_detected_backend_hardware_effects_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    class DummyBackend:
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
    # Avoid DBus/TCC calls in the menu builder.
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Effects" not in labels
    assert "Software Color Editor" not in labels
    assert "Support Tools…" in labels
    assert "Debug" not in labels
    assert "Open Debug Tools…" not in labels
    assert "Detect New Backends" not in labels
    assert "Open Backend Discovery…" not in labels


def test_menu_hides_uniform_color_picker_when_color_capability_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False, color=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    labels = [i["text"] for i in items if isinstance(i, dict)]

    assert "Hardware Static Mode" in labels
    assert "Hardware Uniform Color…" not in labels
    assert "Hardware Effects" not in labels


def test_menu_includes_keyboard_status_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    # First entry should be the keyboard device selector.
    assert isinstance(items[0], dict)
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


def test_menu_includes_lightbar_status_header_when_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
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

    assert items[1]["text"] == "Lightbar: ITE Device(8233) (048d:7001) [experimental disabled]"


def test_menu_switches_body_when_lightbar_context_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

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

    assert "Hardware Static Mode" not in labels
    assert "Software Effects" not in labels
    assert "Lightbar backend is present but disabled by experimental-backend policy" in labels
    assert "Support Tools…" in labels
    assert "Quit" in labels


def test_menu_uses_lightbar_context_builder_when_controls_are_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

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

    assert "Color…" in labels
    assert "Brightness" in labels
    assert "Turn Off" in labels
    assert "Support Tools…" in labels
    assert "Quit" in labels


def test_menu_includes_software_target_submenu_when_keyboard_context_is_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

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
    submenu = next(i["action"] for i in items if isinstance(i, dict) and i["text"] == "Software Targets")
    labels = [i["text"] for i in submenu.items if isinstance(i, dict)]

    assert labels == ["Keyboard Only", "All Compatible Devices"]


def test_software_target_submenu_actions_use_pystray_compatible_arity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

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
    submenu = next(i["action"] for i in items if isinstance(i, dict) and i["text"] == "Software Targets")
    first_action = next(i["action"] for i in submenu.items if isinstance(i, dict) and i["text"] == "Keyboard Only")

    assert first_action.__code__.co_argcount == 2


def test_menu_resets_invalid_selected_context_to_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.selected_device_context = "missing:device"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert tray.selected_device_context == "keyboard"
    assert tray.config.tray_device_context == "keyboard"
    assert "Keyboard" in items[0]["text"]


def test_keyboard_status_badges_research_backed_experimental_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    class DummyBackend:
        name = "ite8910"
        stability = "experimental"
        experimental_evidence = "reverse_engineered"

    class DummyProbe:
        identifiers = {"usb_vid": "0x048d", "usb_pid": "0x8910"}

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
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.engine.device_available = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "not detected" in items[0]["text"].lower()


def test_menu_includes_active_mode_indicator_between_off_and_quit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_tray_active_indicator_shows_perkey_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: "light")

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))
    tray.config.effect = "perkey"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    # Mode indicator should show "software" and the profile name
    mode_text = items[-2]["text"].lower()
    assert "mode:" in mode_text
    assert "software" in mode_text
    assert "light" in mode_text


def test_tray_active_indicator_falls_back_to_unknown_when_profile_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "list_profiles", lambda: [])
    monkeypatch.setattr(tray_menu.tcc_power_profiles, "get_active_profile", lambda: None)

    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "get_active_profile", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))
    tray.config.effect = "perkey"
    tray.is_off = False

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    mode_text = items[-2]["text"].lower()

    assert "mode:" in mode_text
    assert "software" in mode_text
    assert "unknown" in mode_text


def test_tcc_profiles_menu_returns_none_when_tcc_query_raises_runtime_error() -> None:
    from src.tray.ui import menu_sections

    class BrokenTcc:
        def list_profiles(self):
            raise RuntimeError("boom")

        def get_active_profile(self):
            return None

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))

    assert (
        menu_sections.build_tcc_profiles_menu(
            tray,
            pystray=FakePystray,
            item=fake_item,
            tcc=BrokenTcc(),
        )
        is None
    )


def test_system_power_mode_menu_returns_none_when_status_lookup_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.ui import menu_sections

    monkeypatch.setattr(menu_sections, "get_status", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))

    assert (
        menu_sections.build_system_power_mode_menu(
            tray,
            pystray=FakePystray,
            item=fake_item,
        )
        is None
    )


def test_perkey_profiles_menu_falls_back_to_editor_when_profile_listing_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.ui import menu_sections
    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(core_profiles, "list_profiles", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    tray = DummyTray(DummyCaps(per_key=True, hardware_effects=False))

    menu = menu_sections.build_perkey_profiles_menu(
        tray,
        pystray=FakePystray,
        item=fake_item,
        per_key_supported=True,
    )

    assert isinstance(menu, FakeMenu)
    assert [entry["text"] for entry in menu.items if isinstance(entry, dict)] == ["Open Color Editor…"]
