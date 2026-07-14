"""Phase 0 regression & terminology contracts for issue #7.

Issue: https://github.com/Rainexn0b/keyRGB/issues/7
Plan: ``docs/I-implementation-plans/
secondary-lighting-profile-editor-and-simulation-plan.md`` (Phase 0).

Reporter state (Lenovo Legion Pro 7 16IAX10H, ``0x048d:0xc197``):

- the ``ite8258_perkey_chassis_logo_neon_vent_lenovo_legion`` parent is available;
- Logo / Neon Strip / Vents virtual routes are available and uniform-capable;
- per-route colour/brightness state exists in config;
- the saved software-effect target is ``all_uniform_capable``;
- animated software output therefore reaches the routes, but Static does not
  restore them.

These tests lock the *current* behaviour so later phases can prove they changed
exactly the right seam. They do **not** change any source. The intended
post-fix semantics are recorded as a mode table (see ``_ISSUE7_MODE_TABLE``)
and referenced from each test so a future refactor cannot silently conflate
Static application with animated-effect output again.

The implementation phases are complete, so intended-behaviour contracts are
ordinary passing tests rather than stale expected failures.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core import secondary_device_routes
from src.core.effects.catalog import REACTIVE_EFFECTS
from src.core.secondary_device_runtime import EffectiveSecondaryRoute
from src.core.effects.software_targets import (
    SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
    SOFTWARE_EFFECT_TARGET_KEYBOARD,
    normalize_software_effect_target,
    software_render_targets,
)
from src.core.secondary_device_routes import iter_virtual_routes
from src.core.secondary_device_routes import BRIGHTNESS_POLICY_PRIMARY_SHARED
from src.core.utils.safe_attrs import safe_bool_attr, safe_int_attr, safe_str_attr
from src.tray.controllers import _software_target_auxiliary, software_target_controller
from src.tray.controllers.software_target_controller import (
    apply_software_effect_target_selection,
    restore_secondary_software_targets,
    secondary_software_render_targets,
)
from src.tray.pollers.config_polling_internal._config_apply_state import (
    _safe_perkey_signature,
    _safe_tuple_attr,
    build_config_apply_state,
)
from src.tray.ui import _menu_status_devices

# The issue #7 mode table. Static application owns the saved scene; animated
# effects render over it and must not redefine it. Copied from the plan so the
# intent travels with the tests.
_ISSUE7_MODE_TABLE = """
| Situation                         | Keyboard     | Enabled secondary routes      | Disabled secondary routes |
|-----------------------------------|--------------|-------------------------------|---------------------------|
| Static uniform / per-key          | Profile      | Profile static colour         | Off                       |
| Software animation, keyboard only | Animated     | Profile static colour         | Off                       |
| Software animation, keyboard+areas| Animated     | Uniformized animated output   | Off                       |
| Stop software animation           | Restore prof.| Restore profile static colour | Off                       |
| Keyboard hardware effect          | Hardware fx  | Profile static colour         | Off                       |

Invariant: Static application must NOT inspect ``software_effect_target``;
that setting controls animated software output only.
"""

_VIRTUAL_DEVICE_TYPES = ("logo", "neon", "vent")
_VIRTUAL_STATE_KEYS = tuple(f"ite8258_chassis_{zone}" for zone in _VIRTUAL_DEVICE_TYPES)
_VIRTUAL_BACKEND_KEYS = tuple(f"ite8258-chassis-{zone}" for zone in _VIRTUAL_DEVICE_TYPES)

# Distinct saved colours per route so tests can prove each row is independent.
_SAVED_COLORS = {
    "logo": (255, 0, 0),
    "neon": (0, 255, 0),
    "vent": (0, 0, 255),
}
_SAVED_BRIGHTNESS = 25


class _SpyZoneDevice:
    """Records set_color / turn_off / close for one virtual zone device.

    Mirrors the uniform-device contract used by the cached secondary software
    target so it can stand in for a real zone device without any hardware.
    """

    supports_per_key = False

    def __init__(self, zone: str, sink: list[tuple[str, str, tuple[int, ...], int]]) -> None:
        self._zone = zone
        self._sink = sink

    def set_color(self, color: object, *, brightness: int) -> None:
        self._sink.append((self._zone, "set_color", tuple(color), int(brightness)))  # type: ignore[arg-type]

    def turn_off(self) -> None:
        self._sink.append((self._zone, "turn_off", (), 0))

    def close(self) -> None:  # pragma: no cover - exercised only on failure paths
        self._sink.append((self._zone, "close", (), 0))


class _Issue7State(SimpleNamespace):
    """Bundle of observable artefacts returned by the issue #7 fixture factory."""

    tray: Any
    applied: list[tuple[str, str, tuple[int, ...], int]]
    spy_devices: dict[str, _SpyZoneDevice]


@pytest.fixture
def issue7_factory(monkeypatch: pytest.MonkeyPatch):
    """Build sanitized issue #7 state.

    Patches the three ``route_for_context_entry`` binding sites (core, auxiliary,
    controller) and parent availability so the three virtual routes resolve to
    spy zone devices without touching real hardware or USB. Returns a builder
    so each test can select the effect-output target and the forced-off flag.
    """

    original_route_for_context_entry = secondary_device_routes.route_for_context_entry

    def _make(*, target: str = SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE, is_off: bool = False) -> _Issue7State:
        applied: list[tuple[str, str, tuple[int, ...], int]] = []
        spy_devices = {zone: _SpyZoneDevice(zone=zone, sink=applied) for zone in _VIRTUAL_DEVICE_TYPES}
        state = _Issue7State(tray=None, applied=applied, spy_devices=spy_devices)

        # Defined inside ``_make`` so the ``get_device`` closure resolves the
        # per-build spy set rather than a shared fixture-scope binding.
        def _fake_route_for_context_entry(context_entry: object) -> Any:
            device_type = str(_entry_get(context_entry, "device_type") or "").strip().lower()
            if device_type in _VIRTUAL_DEVICE_TYPES:
                return SimpleNamespace(
                    device_type=device_type,
                    state_key=f"ite8258_chassis_{device_type}",
                    config_brightness_attr=f"ite8258_chassis_{device_type}_brightness",
                    config_color_attr=f"ite8258_chassis_{device_type}_color",
                    supports_uniform_color=True,
                    supports_software_target=True,
                    supports_profile_state=True,
                    brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
                    get_device=lambda zone=device_type: spy_devices[zone],
                )
            return original_route_for_context_entry(context_entry)  # type: ignore[arg-type]

        normalized_target = normalize_software_effect_target(target)

        def _get_secondary_device_brightness(state_key, *, fallback_keys=(), default=0):
            return _SAVED_BRIGHTNESS

        def _get_secondary_device_color(state_key, *, fallback_keys=(), default=(255, 0, 0)):
            for zone, color in _SAVED_COLORS.items():
                if state_key == f"ite8258_chassis_{zone}":
                    return color
            return default

        tray = SimpleNamespace(
            config=SimpleNamespace(
                software_effect_target=normalized_target,
                brightness=_SAVED_BRIGHTNESS,
                lightbar_brightness=0,
                lightbar_color=(0, 0, 0),
                get_secondary_device_enabled=lambda *_args, **_kwargs: True,
                get_secondary_device_brightness=_get_secondary_device_brightness,
                get_secondary_device_color=_get_secondary_device_color,
            ),
            engine=SimpleNamespace(
                software_effect_target=normalized_target,
                secondary_software_targets_provider=None,
                kb=None,
                device_available=True,
                _ensure_device_available=lambda: True,
                mark_device_unavailable=lambda: None,
            ),
            backend=None,
            backend_probe=None,
            device_discovery={"candidates": []},
            secondary_device_controls={},
            is_off=bool(is_off),
            _last_brightness=0,
            _log_event=MagicMock(),
            _log_exception=MagicMock(),
            _notify_permission_issue=MagicMock(),
        )
        state.tray = tray

        # Parent availability: the composite ITE 8258 chassis parent is present.
        monkeypatch.setattr(
            _menu_status_devices,
            "iter_effective_secondary_routes",
            lambda: tuple(
                EffectiveSecondaryRoute(
                    route=route,
                    available=True,
                    simulated=False,
                    availability_source="test",
                )
                for route in iter_virtual_routes()
            ),
        )

        # Route resolution: the three virtual zones resolve to spy devices at
        # every binding site that production code reaches.
        monkeypatch.setattr(secondary_device_routes, "route_for_context_entry", _fake_route_for_context_entry)
        monkeypatch.setattr(_software_target_auxiliary, "route_for_context_entry", _fake_route_for_context_entry)
        monkeypatch.setattr(software_target_controller, "route_for_context_entry", _fake_route_for_context_entry)

        # Install the engine provider exactly the way the live tray does, so
        # the engine-level fan-out path is exercised realistically.
        software_target_controller.configure_engine_software_targets(tray)

        return state

    return _make


def _entry_get(context_entry: object, key: str) -> object:
    getter = getattr(context_entry, "get", None)
    if callable(getter):
        return getter(key)
    return getattr(context_entry, key, None)


# ---------------------------------------------------------------------------
# Characterization: route inventory produces individual rows.
# ---------------------------------------------------------------------------
def test_issue7_route_inventory_produces_three_individual_rows(issue7_factory) -> None:
    """Route inventory yields one distinct row per virtual zone.

    Mode table: each enabled secondary route is an individual lighting area, not
    a keyboard cell. The three composite-controller zones (Logo / Neon / Vents)
    must surface as three rows, never collapsed or duplicated.
    """
    state = issue7_factory()

    targets = secondary_software_render_targets(state.tray)

    assert [target.key for target in targets] == list(_VIRTUAL_BACKEND_KEYS)
    # State keys are the stable profile-storage identifiers and must be unique.
    assert len(_VIRTUAL_STATE_KEYS) == len(set(_VIRTUAL_STATE_KEYS))


def test_issue7_route_inventory_rows_match_registered_virtual_routes(issue7_factory) -> None:
    """The inventory rows correspond exactly to the registered virtual routes."""
    state = issue7_factory()

    targets = secondary_software_render_targets(state.tray)
    registered = {route.device_type: route for route in iter_virtual_routes()}

    # Keys are ``ite8258-chassis-<zone>``; derive the zone to cross-check against
    # the registered route table without depending on protocol-internal fields.
    def _zone_for_key(key: str) -> str:
        return key.rsplit("-", 1)[-1]

    assert {_zone_for_key(target.key) for target in targets} == set(registered)
    for target in targets:
        route = registered[_zone_for_key(target.key)]
        assert route.supports_uniform_color is True
        assert route.supports_software_target is True


# ---------------------------------------------------------------------------
# Characterization: animated uniform fan-out reaches all three routes.
# ---------------------------------------------------------------------------
def test_issue7_animated_fanout_reaches_all_three_virtual_routes(issue7_factory) -> None:
    """Animated software output under ``all_uniform_capable`` reaches every route.

    Mode table: "Software animation, keyboard + areas" must uniformize output to
    enabled routes. This is the part of issue #7 that already works and must keep
    working through the refactor.
    """
    state = issue7_factory(target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE)

    targets = software_render_targets(state.tray.engine)

    secondary = targets[1:]  # index 0 is the keyboard target
    assert {target.key for target in secondary} == set(_VIRTUAL_BACKEND_KEYS)
    assert all(target.device is not None for target in secondary)


# ---------------------------------------------------------------------------
# Characterization: the restore building block is target-agnostic.
# ---------------------------------------------------------------------------
def test_issue7_restore_function_is_target_agnostic(issue7_factory) -> None:
    """``restore_secondary_software_targets`` reaches routes regardless of target.

    Mode table invariant: Static application must NOT inspect
    ``software_effect_target``. The restore function itself already honours this
    (it applies saved per-route state without checking the animated-effect
    target). This test pins that building-block property so the contract is
    preserved; the gap is only in the *caller* gating (see the next test).
    """
    state = issue7_factory(target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE)

    restore_secondary_software_targets(state.tray)

    assert len(state.applied) == 3
    zones_written = {entry[0] for entry in state.applied}
    assert zones_written == set(_VIRTUAL_DEVICE_TYPES)
    # Each route received its own saved colour, proving the rows are independent.
    for zone, color in _SAVED_COLORS.items():
        zone_writes = [e for e in state.applied if e[0] == zone]
        assert zone_writes, f"no write recorded for {zone}"
        assert zone_writes[0][1] == "set_color"
        assert zone_writes[0][2] == color
        assert zone_writes[0][3] == _SAVED_BRIGHTNESS


# ---------------------------------------------------------------------------
# Contract: entering animated fan-out does not restore static output, while
# leaving fan-out restores the static scene. Static mode itself is handled by
# the dedicated secondary-static-scene controller and is target-independent.
# ---------------------------------------------------------------------------
def test_issue7_target_selection_restores_static_only_when_leaving_fanout(issue7_factory) -> None:
    """The animation target toggle restores areas only when fan-out stops."""
    state = issue7_factory(target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE)

    # Selecting "all" (entering animation fan-out): restore is NOT invoked.
    apply_software_effect_target_selection(state.tray, SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE)
    assert state.applied == []

    # Switching back to "keyboard" (leaving fan-out): restore IS invoked and
    # reaches every route with its saved colour.
    apply_software_effect_target_selection(state.tray, SOFTWARE_EFFECT_TARGET_KEYBOARD)
    assert len(state.applied) == 3
    assert {entry[0] for entry in state.applied} == set(_VIRTUAL_DEVICE_TYPES)
    for zone, color in _SAVED_COLORS.items():
        zone_writes = [e for e in state.applied if e[0] == zone]
        assert zone_writes and zone_writes[0][2] == color


# ---------------------------------------------------------------------------
# Contract (Phase 5): the config-poller signature observes secondary-only
# changes through the normalized ``secondary_device_state`` mirror.
# ---------------------------------------------------------------------------
def test_issue7_config_apply_state_reflects_secondary_only_changes() -> None:
    """A secondary-only config change must change the poller signature.

    Mode table: editing a Lighting area in the editor process must be observed
    and applied by the tray without an unrelated keyboard/config change. Today
    ``build_config_apply_state`` reads no secondary attributes, so two configs
    that differ only in Logo colour must produce different signatures.
    """

    def resolve_effect_name(effect_name: str) -> str:
        return effect_name

    reactive_effects_set: frozenset[str] = frozenset(REACTIVE_EFFECTS)

    def _build_state(config: object) -> Any:
        return build_config_apply_state(
            config,
            resolve_effect_name=resolve_effect_name,
            read_bool_attr=safe_bool_attr,
            read_int_attr=safe_int_attr,
            read_str_attr=safe_str_attr,
            read_tuple_attr=_safe_tuple_attr,
            read_perkey_signature=_safe_perkey_signature,
            normalize_software_effect_target_fn=normalize_software_effect_target,
            reactive_effects_set=reactive_effects_set,
        )

    config_a = SimpleNamespace(
        effect="none",
        speed=0,
        brightness=40,
        color=(255, 255, 255),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(255, 255, 255),
        software_effect_target=SOFTWARE_EFFECT_TARGET_KEYBOARD,
        _settings={
            "secondary_device_state": {"ite8258_chassis_logo": {"enabled": True, "color": list(_SAVED_COLORS["logo"])}}
        },
    )
    config_b = SimpleNamespace(
        effect="none",
        speed=0,
        brightness=40,
        color=(255, 255, 255),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(255, 255, 255),
        software_effect_target=SOFTWARE_EFFECT_TARGET_KEYBOARD,
        _settings={
            "secondary_device_state": {
                # Same as config_a except for the Logo area colour only.
                "ite8258_chassis_logo": {"enabled": True, "color": [123, 45, 67]}
            }
        },
    )

    state_a = _build_state(config_a)
    state_b = _build_state(config_b)

    assert state_a != state_b
