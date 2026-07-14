from __future__ import annotations

from dataclasses import dataclass

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.tray.ui import menu as tray_menu
from src.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)


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
    assert "Support Tools…" in labels
    assert "Debug" not in labels
    assert "Open Debug Tools…" not in labels
    assert "Detect New Backends" not in labels
    assert "Open Backend Discovery…" not in labels


def test_menu_keeps_lighting_editor_for_uniform_keyboard_with_secondary_device(monkeypatch) -> None:
    monkeypatch.setattr(tray_menu, "has_available_secondary_profile_routes", lambda: True)
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
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
        identifiers = {"usb_vid": "0x048d", "usb_pid": "0x600b"}

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.backend = DummyBackend()
    tray.backend_probe = DummyProbe()

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)
    assert "048d:600b" in items[0]["text"].lower()


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
    assert "Support Tools…" in labels
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
    assert "Support Tools…" in labels
    assert "Quit" in labels


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
        "Support Tools…",
        "Settings",
        "Turn Off",
        "Quit",
    ]
    positions = [labels.index(label) for label in expected]
    assert positions == sorted(positions)


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


def test_menu_resets_invalid_selected_context_to_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    tray.selected_device_context = "missing:device"

    items = tray_menu.build_menu_items(tray, pystray=FakePystray, item=fake_item)

    assert tray.selected_device_context == "keyboard"
    assert tray.config.tray_device_context == "keyboard"
    assert "Keyboard" in items[0]["text"]


def test_keyboard_status_badges_research_backed_experimental_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyBackend:
        name = "ite8910_perkey"
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


def test_tray_active_indicator_falls_back_to_unknown_when_profile_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_system_power_menu_contains_power_mode_settings_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tray.ui import menu_sections

    monkeypatch.setattr(
        menu_sections,
        "get_status",
        lambda: type("Status", (), {"supported": True, "identifiers": {"can_apply": "true"}, "mode": None})(),
    )

    tray = DummyTray(DummyCaps(per_key=False, hardware_effects=False))
    power_menu = menu_sections.build_system_power_mode_menu(tray, pystray=FakePystray, item=fake_item)

    assert isinstance(power_menu, FakeMenu)
    labels = [entry["text"] for entry in power_menu.items if isinstance(entry, dict)]
    assert labels[-1] == "Power Mode Settings…"


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
    assert [entry["text"] for entry in menu.items if isinstance(entry, dict)] == ["Lighting Profile Editor"]
