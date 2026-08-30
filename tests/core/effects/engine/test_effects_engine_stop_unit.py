from __future__ import annotations

import logging
import threading
import time
from threading import Event

import pytest

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


def test_start_effect_stops_previous_software_thread() -> None:
    engine = EffectsEngine()

    # Avoid touching real hardware.
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.start_effect("rainbow_wave", speed=0, brightness=25, color=(255, 0, 0))
    first_thread = engine.thread
    assert first_thread is not None

    # Immediately switch effects; the first thread must not keep running.
    engine.start_effect("spectrum_cycle", speed=0, brightness=25, color=(255, 0, 0))
    second_thread = engine.thread
    assert second_thread is not None
    assert second_thread is not first_thread

    # With stop_event-based waiting, the old thread should exit promptly.
    deadline = time.monotonic() + 0.5
    while first_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert not first_thread.is_alive()

    engine.stop()


def test_software_effect_fades_between_colors() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[tuple[tuple[int, int, int], int]] = []

        def set_color(self, color, *, brightness: int):
            r, g, b = color
            self.calls.append(((int(r), int(g), int(b)), int(brightness)))

    engine = EffectsEngine()

    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    engine.current_color = (255, 0, 0)
    engine.start_effect("strobe", speed=5, brightness=25, color=(0, 0, 255))

    # Fade should produce multiple intermediate frames and include the target color.
    assert len(spy.calls) >= 2
    assert (0, 0, 255) in [rgb for (rgb, _b) in spy.calls]
    engine.stop()


def test_fade_to_non_black_never_writes_full_black() -> None:
    class SpyKeyboard(NullKeyboard):
        def __init__(self):
            self.calls: list[tuple[tuple[int, int, int], int]] = []

        def set_color(self, color, *, brightness: int):
            r, g, b = color
            self.calls.append(((int(r), int(g), int(b)), int(brightness)))

    engine = EffectsEngine()

    spy = SpyKeyboard()
    engine.kb = spy
    engine.device_available = True
    engine.brightness = 25

    engine._fade_uniform_color(
        from_color=(0, 0, 0),
        to_color=(255, 0, 0),
        brightness=25,
        duration_s=0.02,
        steps=8,
    )

    assert spy.calls
    for rgb, _brightness in spy.calls:
        assert rgb != (0, 0, 0)


def test_fade_uniform_color_stops_nonfatally_on_expected_write_errors() -> None:
    class BrokenKeyboard(NullKeyboard):
        def __init__(self):
            self.calls = 0

        def set_color(self, color, *, brightness: int):
            del color, brightness
            self.calls += 1
            raise OSError("device busy")

    engine = EffectsEngine()
    broken = BrokenKeyboard()
    engine.kb = broken

    engine._fade_uniform_color(
        from_color=(255, 0, 0),
        to_color=(0, 0, 255),
        brightness=25,
        duration_s=0.02,
        steps=4,
    )

    assert broken.calls == 1


def test_fade_uniform_color_propagates_unexpected_errors() -> None:
    class BrokenKeyboard(NullKeyboard):
        def set_color(self, color, *, brightness: int):
            del color, brightness
            raise LookupError("unexpected fade bug")

    engine = EffectsEngine()
    engine.kb = BrokenKeyboard()

    with pytest.raises(LookupError, match="unexpected fade bug"):
        engine._fade_uniform_color(
            from_color=(255, 0, 0),
            to_color=(0, 0, 255),
            brightness=25,
            duration_s=0.02,
            steps=4,
        )


def test_stop_resets_rendered_and_mode_brightness_caches() -> None:
    engine = EffectsEngine()
    engine._last_rendered_brightness = 25
    engine._last_hw_mode_brightness = 25

    engine.stop()

    assert engine._last_rendered_brightness is None
    assert engine._last_hw_mode_brightness is None


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


def test_initial_perkey_sw_start_primes_single_frame_without_startup_fade(monkeypatch) -> None:
    """Initial SW startup writes one hidden frame instead of animating the deck."""

    class PerKeyKeyboard(NullKeyboard):
        def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
            del brightness, enable_user_mode

    engine = EffectsEngine()
    engine.backend_caps = _backend_caps(per_key=True)
    engine.kb = PerKeyKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.per_key_colors = {(0, 0): (0, 255, 255)}
    engine.brightness = 10

    calls: list[str] = []
    monkeypatch.setattr(engine, "_prime_per_key_frame", lambda: calls.append("prime") or True)
    monkeypatch.setattr(engine, "_fade_in_per_key", lambda **_kwargs: calls.append("fade"))

    engine._start_sw_effect(
        target=lambda: None,
        prev_color=(0, 0, 0),
        fade_to_color=(0, 255, 255),
    )

    assert calls == ["prime"]
    assert engine._last_hw_mode_brightness == 10
    assert engine._last_rendered_brightness == 10
    engine.stop()


def test_soft_on_start_after_turn_off_primes_with_user_mode_reassert(monkeypatch) -> None:
    """Idle/menu soft-on starts at brightness=1 after turn_off must still prime.

    Historically brightness==1 skipped the per-key prime and only called
    enable_user_mode(0), so ITE boards stayed dark after screen-idle turn-off
    until the user toggled the tray Turn Off item.
    """

    class PerKeyKeyboard(NullKeyboard):
        def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
            del brightness, enable_user_mode

    engine = EffectsEngine()
    engine.backend_caps = _backend_caps(per_key=True)
    engine.kb = PerKeyKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.per_key_colors = {(0, 0): (0, 255, 255)}
    engine.brightness = 1  # SOFT_ON_START_BRIGHTNESS
    engine._device_mode_off = True

    calls: list[str] = []
    monkeypatch.setattr(engine, "_prime_per_key_frame", lambda: calls.append("prime") or True)
    monkeypatch.setattr(engine, "_fade_in_per_key", lambda **_kwargs: calls.append("fade"))

    engine._start_sw_effect(
        target=lambda: None,
        prev_color=(0, 0, 0),
        fade_to_color=(0, 255, 255),
    )

    assert calls == ["prime"]
    assert engine._device_mode_off is False
    assert engine._last_hw_mode_brightness == 1
    engine.stop()


def test_soft_on_start_after_firmware_sleep_primes_without_device_mode_off(monkeypatch) -> None:
    """Controller-sleep restore soft-on must prime even when _device_mode_off is False.

    Firmware sleep reports brightness=0 with is_off=False, so the engine never
    saw an explicit turn_off. Soft-on at brightness=1 must still prime (and the
    prime method reasserts user mode for soft-on).
    """

    class PerKeyKeyboard(NullKeyboard):
        def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
            del brightness, enable_user_mode

    engine = EffectsEngine()
    engine.backend_caps = _backend_caps(per_key=True)
    engine.kb = PerKeyKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.per_key_colors = {(0, 0): (0, 255, 255)}
    engine.brightness = 1  # SOFT_ON_START_BRIGHTNESS
    engine._device_mode_off = False  # firmware sleep path

    calls: list[str] = []
    monkeypatch.setattr(engine, "_prime_per_key_frame", lambda: calls.append("prime") or True)
    monkeypatch.setattr(engine, "_fade_in_per_key", lambda **_kwargs: calls.append("fade"))

    engine._start_sw_effect(
        target=lambda: None,
        prev_color=(0, 0, 0),
        fade_to_color=(0, 255, 255),
    )

    assert calls == ["prime"]
    assert engine._last_hw_mode_brightness == 1
    engine.stop()


def test_soft_on_uniform_start_after_turn_off_reasserts_via_fade(monkeypatch) -> None:
    """Soft-on without a per-key map must still re-enable user mode after turn_off."""

    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.per_key_colors = None
    engine.brightness = 1  # SOFT_ON_START_BRIGHTNESS
    engine._device_mode_off = True

    calls: list[str] = []
    monkeypatch.setattr(
        engine,
        "_fade_uniform_color",
        lambda **_kwargs: calls.append("fade_uniform"),
    )

    engine._start_sw_effect(
        target=lambda: None,
        prev_color=(0, 0, 0),
        fade_to_color=(0, 255, 255),
    )

    assert calls == ["fade_uniform"]
    assert engine._device_mode_off is False
    assert engine._last_rendered_brightness == 1
    engine.stop()


def test_sw_to_sw_transition_skips_fade_in() -> None:
    """SW→SW transitions must skip _fade_in_per_key to avoid a dark-dip flicker.

    When the previous effect was a software effect, from_sw_effect=True is passed
    and the entire fade block is skipped.  The test confirms _fade_uniform_color
    and _fade_in_per_key are uncalled during an SW→SW start.
    """
    from unittest.mock import patch

    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.brightness = 25

    fade_in_calls = []
    fade_uniform_calls = []

    # Patch both fade helpers to detect invocations without side effects.
    with (
        patch.object(engine, "_fade_in_per_key", side_effect=lambda **_kw: fade_in_calls.append(True)),
        patch.object(engine, "_fade_uniform_color", side_effect=lambda **_kw: fade_uniform_calls.append(True)),
    ):
        engine._start_sw_effect(
            target=lambda: None,
            prev_color=(255, 0, 0),
            fade_to_color=(0, 0, 255),
            from_sw_effect=True,
        )
        # Brief wait so the thread starts and any erroneous fade would have been called.
        time.sleep(0.05)

    engine.stop()

    assert not fade_in_calls, "_fade_in_per_key must NOT be called on SW→SW transition"
    assert not fade_uniform_calls, "_fade_uniform_color must NOT be called on SW→SW transition"


def test_permission_denied_effect_thread_logs_traceback_and_notifies_callback(caplog) -> None:
    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    seen: list[Exception] = []
    engine._permission_error_cb = lambda exc: seen.append(exc)

    with caplog.at_level(logging.WARNING, logger="keyrgb.core.effects.engine_start"):
        engine._start_sw_effect(
            target=lambda: (_ for _ in ()).throw(PermissionError("denied")),
            prev_color=(0, 0, 0),
            fade_to_color=(255, 0, 0),
        )
        thread = engine.thread
        assert thread is not None
        thread.join(timeout=1.0)

    assert len(seen) == 1
    assert isinstance(seen[0], PermissionError)
    assert engine.running is False
    assert engine.thread is None

    warning_records = [
        record for record in caplog.records if "Permission denied while applying effect" in record.getMessage()
    ]
    assert warning_records
    assert warning_records[-1].exc_info is not None


def test_permission_error_callback_logs_recoverable_runtime_failures(caplog) -> None:
    from keyrgb.core.effects.engine_support.start import _notify_permission_error_callback_best_effort

    class _Engine:
        _permission_error_cb = staticmethod(lambda _exc: (_ for _ in ()).throw(RuntimeError("callback failed")))

    with caplog.at_level(logging.ERROR, logger="keyrgb.core.effects.engine_start"):
        _notify_permission_error_callback_best_effort(_Engine(), PermissionError("denied"))

    records = [record for record in caplog.records if "Permission error callback failed" in record.getMessage()]
    assert records
    assert records[-1].exc_info is not None


def test_permission_error_callback_propagates_unexpected_failures() -> None:
    from keyrgb.core.effects.engine_support.start import _notify_permission_error_callback_best_effort

    class _Engine:
        _permission_error_cb = staticmethod(
            lambda _exc: (_ for _ in ()).throw(AssertionError("unexpected callback bug"))
        )

    with pytest.raises(AssertionError, match="unexpected callback bug"):
        _notify_permission_error_callback_best_effort(_Engine(), PermissionError("denied"))


def test_disconnect_effect_thread_logs_traceback_even_if_marking_unavailable_fails(caplog) -> None:
    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    def fail_mark_unavailable() -> None:
        raise RuntimeError("mark failed")

    engine.mark_device_unavailable = fail_mark_unavailable  # type: ignore[assignment]

    with caplog.at_level(logging.WARNING, logger="keyrgb.core.effects.engine_start"):
        engine._start_sw_effect(
            target=lambda: (_ for _ in ()).throw(OSError(19, "No such device")),
            prev_color=(0, 0, 0),
            fade_to_color=(255, 0, 0),
        )
        thread = engine.thread
        assert thread is not None
        thread.join(timeout=1.0)

    failure_records = [
        record
        for record in caplog.records
        if "Failed to mark keyboard device unavailable after disconnect" in record.getMessage()
    ]
    assert failure_records
    assert failure_records[-1].exc_info is not None

    warning_records = [
        record
        for record in caplog.records
        if "Keyboard device disconnected while applying effect" in record.getMessage()
    ]
    assert warning_records
    assert warning_records[-1].exc_info is not None
    assert engine.running is False
    assert engine.thread is None


def test_effect_thread_propagates_unexpected_failures_to_thread_excepthook(monkeypatch, caplog) -> None:
    engine = EffectsEngine()
    engine.kb = NullKeyboard()
    engine.device_available = False
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]

    seen: list[threading.ExceptHookArgs] = []
    monkeypatch.setattr(threading, "excepthook", seen.append)

    with caplog.at_level(logging.ERROR, logger="keyrgb.core.effects.engine_start"):
        engine._start_sw_effect(
            target=lambda: (_ for _ in ()).throw(AssertionError("unexpected thread bug")),
            prev_color=(0, 0, 0),
            fade_to_color=(255, 0, 0),
        )
        thread = engine.thread
        assert thread is not None
        thread.join(timeout=1.0)

    assert len(seen) == 1
    assert seen[0].exc_type is AssertionError
    assert str(seen[0].exc_value) == "unexpected thread bug"
    assert engine.running is False
    assert engine.thread is None
    assert not [record for record in caplog.records if "Unhandled exception in effect thread" in record.getMessage()]


def test_mark_device_unavailable_logs_recoverable_runtime_failures(caplog) -> None:
    from keyrgb.core.effects.engine_support.start import _mark_device_unavailable_best_effort

    class _Engine:
        @staticmethod
        def mark_device_unavailable() -> None:
            raise RuntimeError("mark failed")

    with caplog.at_level(logging.ERROR, logger="keyrgb.core.effects.engine_start"):
        _mark_device_unavailable_best_effort(_Engine())

    records = [
        record
        for record in caplog.records
        if "Failed to mark keyboard device unavailable after disconnect" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_mark_device_unavailable_propagates_unexpected_failures() -> None:
    from keyrgb.core.effects.engine_support.start import _mark_device_unavailable_best_effort

    class _Engine:
        @staticmethod
        def mark_device_unavailable() -> None:
            raise AssertionError("unexpected mark bug")

    with pytest.raises(AssertionError, match="unexpected mark bug"):
        _mark_device_unavailable_best_effort(_Engine())


def test_managed_effect_thread_join_suppresses_recoverable_cleanup_failures() -> None:
    from keyrgb.core.effects.engine_support.start import _ManagedEffectThread

    class _BrokenEngine:
        @property
        def thread(self):
            raise RuntimeError("thread state failed")

        @thread.setter
        def thread(self, _value) -> None:
            raise RuntimeError("thread state failed")

    thread = _ManagedEffectThread(engine=_BrokenEngine(), target=lambda: None)
    thread.start()
    thread.join(timeout=1.0)


def test_managed_effect_thread_join_propagates_unexpected_cleanup_failures() -> None:
    from keyrgb.core.effects.engine_support.start import _ManagedEffectThread

    class _BrokenEngine:
        @property
        def thread(self):
            raise AssertionError("unexpected thread cleanup bug")

        @thread.setter
        def thread(self, _value) -> None:
            raise AssertionError("unexpected thread cleanup bug")

    thread = _ManagedEffectThread(engine=_BrokenEngine(), target=lambda: None)
    thread.start()
    with pytest.raises(AssertionError, match="unexpected thread cleanup bug"):
        thread.join(timeout=1.0)
