from __future__ import annotations

import threading
import time
from threading import Event

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.effects.catalog import hardware_effect_selection_key
from keyrgb.core.effects.device import NullKeyboard
from keyrgb.core.effects.engine import EffectsEngine


def _effect_builder(effect_name: str, *, extra: tuple[str, ...] = ()):  # type: ignore[no-untyped-def]
    args = {"speed": None, "brightness": None}
    for key in extra:
        args[key] = None

    def build(**kwargs):
        _ = args
        return {"name": effect_name, **kwargs}

    return build


def _backend_caps(*, per_key: bool = False, hardware_effects: bool = False) -> BackendCapabilities:
    return BackendCapabilities(
        brightness=True,
        per_key=per_key,
        color=True,
        hardware_effects=hardware_effects,
        palette=False,
    )


class _HardwareEffectsBackend:
    def capabilities(self) -> BackendCapabilities:
        return _backend_caps(hardware_effects=True)


def test_start_hw_effect_uses_injected_backend_effects() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            return {"snake": _effect_builder("snake", extra=("direction", "color"))}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (9, 8, 7)
    engine.direction = "left"

    engine.start_effect("snake", speed=5, brightness=20, color=(9, 8, 7))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "snake"
    assert payload["color"] == (9, 8, 7)
    assert payload["direction"] == "left"


def test_start_effect_rejects_legacy_generic_hw_name_without_backend_support() -> None:
    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    try:
        engine.start_effect("wave", speed=5, brightness=20, color=(9, 8, 7))
    except ValueError as exc:
        assert "Unknown effect: wave" in str(exc)
    else:
        raise AssertionError("Expected legacy generic hardware name to be rejected")


def test_start_effect_accepts_backend_exposed_hw_name() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            return {"wave": _effect_builder("wave", extra=("color",))}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (3, 2, 1)

    engine.start_effect("wave", speed=5, brightness=20, color=(3, 2, 1))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "wave"
    assert payload["color"] == (3, 2, 1)


class _FadeSleepGate:
    """Park a brightness fade between steps, where it holds no lock.

    ``_fade_brightness`` sleeps outside ``kb_lock``, so parking there lets a
    replacement ``start_effect()`` run to completion on the main thread — the
    exact interleaving KSW-4 describes — without any lock contention timing.
    """

    def __init__(self) -> None:
        self.parked = Event()
        self.release = Event()
        self._gate_armed = True

    def sleep(self, _seconds: float) -> None:
        if not self._gate_armed:
            return
        self._gate_armed = False
        self.parked.set()
        assert self.release.wait(timeout=5.0), "fade gate was never released"


def test_start_effect_invalidates_in_flight_turn_off_fade(monkeypatch) -> None:
    """A replacement effect must survive a concurrent fading turn_off.

    A screen-dim/idle ``turn_off(fade=True)`` runs on the power thread. If a
    replacement ``start_effect()`` lands mid-fade, the old operation must commit
    neither further brightness steps nor its terminal ``kb.turn_off()``.
    """

    import keyrgb.core.effects.engine_support.brightness as brightness_mod

    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.brightness_writes: list[int] = []
            self.turn_off_calls = 0
            self.payloads: list[object] = []

        def set_brightness(self, brightness: int) -> None:
            self.brightness_writes.append(int(brightness))

        def turn_off(self) -> None:
            self.turn_off_calls += 1

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            return {"wave": _effect_builder("wave", extra=("color",))}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.brightness = 40
    engine._device_mode_off = False

    gate = _FadeSleepGate()
    # Replace the module-level ``time`` name so only brightness fades are parked.
    monkeypatch.setattr(brightness_mod, "time", gate)

    fader = threading.Thread(target=lambda: engine.turn_off(fade=True, fade_duration_s=0.2), daemon=True)
    fader.start()
    assert gate.parked.wait(timeout=5.0), "turn_off never started fading"
    writes_before_replacement = list(spy.brightness_writes)
    assert writes_before_replacement, "expected at least one pre-replacement fade step"

    # Replacement effect takes ownership of brightness output.
    engine.start_effect("wave", speed=5, brightness=25, color=(3, 2, 1))
    assert spy.payloads

    gate.release.set()
    fader.join(timeout=5.0)
    assert not fader.is_alive()

    # No stale step write and no stale terminal off after the replacement start.
    assert spy.brightness_writes == writes_before_replacement
    assert spy.turn_off_calls == 0
    assert engine._device_mode_off is False
    assert engine.current_effect == "wave"
    assert engine.brightness == 25


def test_start_effect_prefers_software_for_hw_sw_name_collision() -> None:
    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            return {"spectrum_cycle": _effect_builder("hw_spectrum_cycle")}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.start_effect("spectrum_cycle", speed=5, brightness=20, color=(3, 2, 1))

    assert engine.current_effect == "spectrum_cycle"

    engine.stop()


def test_start_effect_forced_hardware_collision_uses_backend_effect() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.payloads: list[object] = []

        def set_effect(self, effect_data) -> None:
            self.payloads.append(effect_data)

    class DummyBackend(_HardwareEffectsBackend):
        def effects(self):
            return {"spectrum_cycle": _effect_builder("spectrum_cycle")}

        def colors(self):
            return {}

    engine = EffectsEngine(backend=DummyBackend())
    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.current_color = (3, 2, 1)

    engine.start_effect(hardware_effect_selection_key("spectrum_cycle"), speed=5, brightness=20, color=(3, 2, 1))

    assert spy.payloads
    payload = spy.payloads[-1]
    assert payload["name"] == "spectrum_cycle"


def test_old_effect_thread_cannot_clear_new_thread_state() -> None:
    engine = EffectsEngine()

    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    first_started = Event()
    first_release = Event()
    second_started = Event()

    def slow_first() -> None:
        first_started.set()
        while not first_release.is_set():
            time.sleep(0.01)

    def long_second() -> None:
        second_started.set()
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline and engine.running and not engine.stop_event.is_set():
            time.sleep(0.01)

    engine._start_sw_effect(target=slow_first, prev_color=(0, 0, 0), fade_to_color=(255, 0, 0))
    first_thread = engine.thread
    assert first_thread is not None
    assert first_started.wait(timeout=0.2)

    engine._start_sw_effect(target=long_second, prev_color=(0, 0, 0), fade_to_color=(255, 0, 0))
    second_thread = engine.thread
    assert second_thread is not None
    assert second_thread is not first_thread
    assert second_started.wait(timeout=0.2)

    first_release.set()
    first_thread.join(timeout=1.0)
    assert not first_thread.is_alive()

    time.sleep(0.05)
    assert engine.running is True

    engine.stop()
