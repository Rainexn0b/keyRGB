from __future__ import annotations

from types import SimpleNamespace

from src.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT, SecondaryDeviceRoute
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.gui.perkey.secondary_lighting import SecondaryLightingDraft
from src.gui.perkey.editor import PerKeyEditor
from src.gui.perkey.ui import lighting_areas


def _draft() -> SecondaryLightingDraft:
    route = SecondaryDeviceRoute(
        device_type="logo",
        backend_name="logo-backend",
        display_name="Logo",
        state_key="logo",
        get_backend=lambda: object(),
        get_device=lambda: object(),
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
    )
    effective = EffectiveSecondaryRoute(
        route=route,
        available=True,
        simulated=True,
        availability_source="simulation",
    )
    return SecondaryLightingDraft(
        {"version": 1, "areas": {"logo": {"enabled": True, "color": [1, 2, 3]}}},
        effective_routes=(effective,),
    )


class _Variable:
    def __init__(self, value="") -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


def test_shared_wheel_updates_only_selected_lighting_area() -> None:
    panel = lighting_areas.LightingAreasPanel.__new__(lighting_areas.LightingAreasPanel)
    panel.editor = SimpleNamespace(secondary_lighting=None, _last_non_black_color=(1, 1, 1))
    panel._draft = _draft()
    panel._selection = _Variable("logo")
    refreshed: list[tuple[str, tuple[int, int, int]]] = []
    panel._refresh_row_color = lambda key, color: refreshed.append((key, color))

    handled = panel.apply_wheel_color((12, 34, 56), released=False)

    assert handled is True
    assert panel.editor.secondary_lighting["areas"]["logo"]["color"] == [12, 34, 56]
    assert refreshed == [("logo", (12, 34, 56))]
    assert panel.editor._last_non_black_color == (12, 34, 56)


def test_shared_wheel_falls_through_to_keyboard_when_no_area_is_selected() -> None:
    panel = lighting_areas.LightingAreasPanel.__new__(lighting_areas.LightingAreasPanel)
    panel.editor = SimpleNamespace(secondary_lighting=None)
    panel._draft = _draft()
    panel._selection = _Variable("keyboard")

    assert panel.apply_wheel_color((12, 34, 56), released=False) is False


def test_lighting_area_rgb_text_matches_keyboard_decimal_format() -> None:
    assert lighting_areas._rgb_text((12, 34, 56)) == "RGB: 12, 34, 56"


def test_independent_lighting_area_brightness_updates_editor_draft(monkeypatch) -> None:
    statuses: list[str] = []
    panel = lighting_areas.LightingAreasPanel.__new__(lighting_areas.LightingAreasPanel)
    panel.editor = SimpleNamespace(secondary_lighting=None)
    panel._draft = _draft()
    monkeypatch.setattr(lighting_areas, "set_status", lambda _editor, message: statuses.append(message))

    panel._brightness_changed("logo", _Variable("35"))

    assert panel.editor.secondary_lighting["areas"]["logo"]["brightness"] == 35
    assert statuses == ["logo brightness set to 35"]


def test_keyboard_selector_restores_selected_keyboard_target(monkeypatch) -> None:
    finalized: list[str] = []
    panel = lighting_areas.LightingAreasPanel.__new__(lighting_areas.LightingAreasPanel)
    panel._selection = _Variable("logo")
    panel.editor = SimpleNamespace(
        selected_slot_id="slot-a",
        selected_key_id="key-a",
        _finalize_selection=finalized.append,
    )

    panel.select_keyboard()

    assert panel._selection.get() == "keyboard"
    assert finalized == ["slot-a"]


def test_editor_routes_wheel_changes_to_selected_lighting_area() -> None:
    calls: list[tuple[tuple[int, int, int], bool]] = []
    editor = PerKeyEditor.__new__(PerKeyEditor)
    editor._lighting_areas_panel = SimpleNamespace(
        apply_wheel_color=lambda color, *, released: calls.append((color, released)) or True
    )

    editor._on_color_change(12, 34, 56)
    editor._on_color_release(65, 43, 21)

    assert calls == [((12, 34, 56), False), ((65, 43, 21), True)]


def test_selecting_keyboard_slot_returns_shared_wheel_to_keyboard(monkeypatch) -> None:
    calls: list[str] = []
    editor = PerKeyEditor.__new__(PerKeyEditor)
    editor._lighting_areas_panel = SimpleNamespace(select_keyboard=lambda: calls.append("keyboard"))
    monkeypatch.setattr(
        "src.gui.perkey.editor.editor_selection.select_slot_id",
        lambda _editor, slot_id: calls.append(slot_id),
    )

    editor.select_slot_id("key-a")

    assert calls == ["keyboard", "key-a"]
