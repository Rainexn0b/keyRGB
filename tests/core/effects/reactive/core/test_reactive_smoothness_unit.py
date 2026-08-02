#!/usr/bin/env python3
"""Unit tests for the reactive typing smoothness upgrades.

Covers:
- plural keypress polling (one pulse per physical press per frame)
- quadratic ease-out pulse decay
- ripple dead-ring skip and diamond-iteration equivalence
- real-dt frame timing helpers
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import src.core.effects.reactive.input as reactive_input
from src.core.effects.matrix_layout import NUM_COLS, NUM_ROWS
from src.core.effects.reactive._ripple_helpers import (
    build_fade_overlay_into,
    build_ripple_overlay_into,
)
from src.core.effects.reactive.utils import (
    _PressSource,
    _Pulse,
    _RainbowPulse,
    _ripple_radius,
    _ripple_weight,
    frame_elapsed_dt_s,
    pulse_decay_ease_out,
    remaining_frame_delay_s,
)


class _FakeDevice:
    def __init__(self, events: list | None = None) -> None:
        self.path = "/dev/input/event3"
        self.closed = 0
        self._events = events or []

    def close(self) -> None:
        self.closed += 1

    def read(self):
        return list(self._events)


def _fake_evdev(key_map: dict[int, str]) -> SimpleNamespace:
    return SimpleNamespace(ecodes=SimpleNamespace(EV_KEY=1, KEY=key_map))


def _fake_select_all(readers, _writers, _errors, _timeout):
    return (list(readers), [], [])


# ── Plural keypress polling ──────────────────────────────────────────────────


def test_poll_keypress_slot_ids_collects_every_press_in_batch(monkeypatch) -> None:
    from src.core.resources.layouts import slot_id_for_key_id

    events = [
        SimpleNamespace(type=1, value=1, code=30),  # KEY_A down
        SimpleNamespace(type=1, value=0, code=30),  # KEY_A up (ignored)
        SimpleNamespace(type=1, value=1, code=48),  # KEY_B down
        SimpleNamespace(type=1, value=2, code=48),  # KEY_B repeat (ignored)
    ]
    device = _FakeDevice(events)

    monkeypatch.setitem(sys.modules, "evdev", _fake_evdev({30: "KEY_A", 48: "KEY_B"}))
    monkeypatch.setitem(sys.modules, "select", SimpleNamespace(select=_fake_select_all))

    slot_ids = reactive_input.poll_keypress_slot_ids([device])

    assert slot_ids == [
        str(slot_id_for_key_id("auto", "a") or "a"),
        str(slot_id_for_key_id("auto", "b") or "b"),
    ]


def test_poll_keypress_slot_id_singular_returns_first_press(monkeypatch) -> None:
    from src.core.resources.layouts import slot_id_for_key_id

    events = [
        SimpleNamespace(type=1, value=1, code=30),
        SimpleNamespace(type=1, value=1, code=48),
    ]
    device = _FakeDevice(events)

    monkeypatch.setitem(sys.modules, "evdev", _fake_evdev({30: "KEY_A", 48: "KEY_B"}))
    monkeypatch.setitem(sys.modules, "select", SimpleNamespace(select=_fake_select_all))

    assert reactive_input.poll_keypress_slot_id([device]) == str(slot_id_for_key_id("auto", "a") or "a")


def test_poll_keypress_slot_ids_empty_for_idle_and_missing_devices(monkeypatch) -> None:
    assert reactive_input.poll_keypress_slot_ids(None) == []
    assert reactive_input.poll_keypress_slot_ids([]) == []

    monkeypatch.setitem(sys.modules, "evdev", _fake_evdev({}))
    monkeypatch.setitem(sys.modules, "select", SimpleNamespace(select=lambda *_a, **_k: ([], [], [])))
    assert reactive_input.poll_keypress_slot_ids([_FakeDevice()]) == []


def test_press_source_poll_slot_ids_synthetic_spawn() -> None:
    press = _PressSource(
        devices=[],
        synthetic=True,
        allow_synthetic=True,
        spawn_interval_s=0.05,
        reopen_interval_s=999.0,
    )

    assert press.poll_slot_ids(dt=0.02) == []
    assert press.poll_slot_ids(dt=0.04) == [""]
    # Singular facade preserved: "" sentinel for synthetic spawns.
    assert press.poll_slot_id(dt=0.05) == ""


def test_press_source_poll_slot_ids_returns_all_real_presses(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.core.effects.reactive.utils.poll_keypress_slot_ids",
        lambda _devices: ["slot-a", "slot-b"],
    )

    press = _PressSource(
        devices=[_FakeDevice()],
        synthetic=False,
        allow_synthetic=False,
        spawn_interval_s=0.05,
    )

    assert press.poll_slot_ids(dt=0.02) == ["slot-a", "slot-b"]
    # Singular facade returns the first press.
    assert press.poll_slot_id(dt=0.02) == "slot-a"


# ── Ease-out pulse decay ─────────────────────────────────────────────────────


def test_pulse_decay_ease_out_curve_shape() -> None:
    assert pulse_decay_ease_out(age_s=0.0, ttl_s=1.0) == 1.0
    assert abs(pulse_decay_ease_out(age_s=0.5, ttl_s=1.0) - 0.5**1.5) < 1e-9
    assert pulse_decay_ease_out(age_s=1.0, ttl_s=1.0) == 0.0
    # Zero slope into black: the last 10% of life contributes almost nothing,
    # but stays brighter than a full quadratic tail would.
    tail = pulse_decay_ease_out(age_s=0.9, ttl_s=1.0)
    assert 0.01 < tail < 0.04
    # Defensive clamps.
    assert pulse_decay_ease_out(age_s=2.0, ttl_s=1.0) == 0.0
    assert pulse_decay_ease_out(age_s=0.5, ttl_s=0.0) == 0.0


def test_build_fade_overlay_into_uses_ease_out_decay() -> None:
    pulse = _Pulse(row=0, col=0, age_s=0.25, ttl_s=0.5)
    dest = build_fade_overlay_into({}, [pulse])
    assert abs(dest[(0, 0)] - 0.5**1.5) < 1e-9  # (1 - 0.5) ** 1.5, not linear 0.5


# ── Ripple overlay: dead-ring skip and diamond equivalence ───────────────────


def _reference_square_overlay(pulses: list[_RainbowPulse], *, band: float) -> dict:
    """Brute-force square scan of the same math the optimised builder uses."""
    dest: dict = {}
    for pulse in pulses:
        max_d = max(pulse.row, NUM_ROWS - 1 - pulse.row) + max(pulse.col, NUM_COLS - 1 - pulse.col)
        if max_d <= 0:
            continue
        intensity = pulse_decay_ease_out(age_s=pulse.age_s, ttl_s=pulse.ttl_s * 1.2)
        if intensity <= 0.0:
            continue
        radius_f = _ripple_radius(age_s=pulse.age_s, ttl_s=pulse.ttl_s, min_radius=0.0, max_radius=float(max_d))
        for r in range(NUM_ROWS):
            for c in range(NUM_COLS):
                d = abs(r - pulse.row) + abs(c - pulse.col)
                w = _ripple_weight(d=d, radius=radius_f, intensity=intensity, band=band)
                if w <= 0.0:
                    continue
                hue = (pulse.hue_offset + (float(d) * 18.0) + (pulse.age_s / pulse.ttl_s) * 360.0) % 360.0
                key = (r, c)
                if key not in dest or w > dest[key][0]:
                    dest[key] = (w, hue)
    return dest


def test_build_ripple_overlay_into_matches_brute_force_reference() -> None:
    pulses = [
        _RainbowPulse(row=2, col=5, age_s=0.2, ttl_s=0.65, hue_offset=10.0),
        _RainbowPulse(row=4, col=15, age_s=0.45, ttl_s=0.65, hue_offset=200.0),
        _RainbowPulse(row=0, col=0, age_s=0.1, ttl_s=0.65, hue_offset=0.0),
    ]

    optimised = build_ripple_overlay_into({}, pulses, band=2.15)
    reference = _reference_square_overlay(pulses, band=2.15)

    assert set(optimised) == set(reference)
    for key, (w, hue) in reference.items():
        opt_w, opt_hue = optimised[key]
        assert abs(opt_w - w) < 1e-9
        assert abs(opt_hue - hue) < 1e-9


def test_build_ripple_overlay_into_wave_reaches_far_corner_from_interior_press() -> None:
    # An interior press near end of life must still light the farthest corner:
    # the radius is normalized to the pulse's own farthest-key distance, so the
    # wave lands at the deck edge instead of dying mid-travel.
    pulse = _RainbowPulse(row=2, col=10, age_s=0.63, ttl_s=0.65, hue_offset=0.0)
    dest = build_ripple_overlay_into({}, [pulse], band=1.0)

    far_corners = [(5, 20), (0, 20), (5, 0), (0, 0)]
    farthest = max(far_corners, key=lambda k: abs(k[0] - 2) + abs(k[1] - 10))
    assert farthest in dest
    weight, _hue = dest[farthest]
    assert weight > 0.0


def test_build_ripple_overlay_into_corner_pulse_lights_until_ttl() -> None:
    # Corner pulses traverse the full 25-key diagonal and stay lit to the end.
    pulse = _RainbowPulse(row=0, col=0, age_s=0.63, ttl_s=0.65, hue_offset=0.0)
    dest = build_ripple_overlay_into({}, [pulse], band=1.0)
    assert (5, 20) in dest


# ── Real-dt frame timing helpers ─────────────────────────────────────────────


def test_frame_elapsed_dt_s_uses_nominal_on_first_frame() -> None:
    assert frame_elapsed_dt_s(now_s=10.0, last_frame_s=None, nominal_dt_s=1.0 / 60.0) == 1.0 / 60.0


def test_frame_elapsed_dt_s_measures_real_delta_and_clamps() -> None:
    assert abs(frame_elapsed_dt_s(now_s=10.033, last_frame_s=10.0, nominal_dt_s=1.0 / 60.0) - 0.033) < 1e-9
    # Stalls (suspend, busy bus) are capped so the animation doesn't teleport.
    assert frame_elapsed_dt_s(now_s=20.0, last_frame_s=10.0, nominal_dt_s=1.0 / 60.0) == 0.25
    # Clock going backwards never ages pulses.
    assert frame_elapsed_dt_s(now_s=9.0, last_frame_s=10.0, nominal_dt_s=1.0 / 60.0) == 0.0


def test_remaining_frame_delay_s_compensates_render_work(monkeypatch) -> None:
    import src.core.effects.reactive.utils as reactive_utils

    monkeypatch.setattr(reactive_utils.time, "monotonic", lambda: 10.006)
    # 6 ms of work in a 16.67 ms frame -> sleep ~10.67 ms, not the full dt.
    remaining = remaining_frame_delay_s(frame_start_s=10.0, nominal_dt_s=1.0 / 60.0)
    assert abs(remaining - (1.0 / 60.0 - 0.006)) < 1e-9

    # Overrun frame -> no negative sleep.
    monkeypatch.setattr(reactive_utils.time, "monotonic", lambda: 10.050)
    assert remaining_frame_delay_s(frame_start_s=10.0, nominal_dt_s=1.0 / 60.0) == 0.0


def test_per_key_mode_policy_env_override(monkeypatch) -> None:
    from types import SimpleNamespace

    from src.core.backends.policies.per_key_mode import (
        PER_KEY_MODE_POLICY_ENV,
        per_key_mode_policy,
        per_key_mode_requires_frame_reassert,
    )

    kb = SimpleNamespace(keyrgb_per_key_mode_policy="reassert_every_frame")

    monkeypatch.delenv(PER_KEY_MODE_POLICY_ENV, raising=False)
    assert per_key_mode_policy(kb) == "reassert_every_frame"
    assert per_key_mode_requires_frame_reassert(kb) is True

    # Diagnostic override wins over the device-declared policy (A/B testing).
    monkeypatch.setenv(PER_KEY_MODE_POLICY_ENV, "init_once")
    assert per_key_mode_policy(kb) == "init_once"
    assert per_key_mode_requires_frame_reassert(kb) is False

    # Unknown values normalize to init_once (same as device-policy behavior).
    monkeypatch.setenv(PER_KEY_MODE_POLICY_ENV, "bogus")
    assert per_key_mode_policy(kb) == "init_once"
