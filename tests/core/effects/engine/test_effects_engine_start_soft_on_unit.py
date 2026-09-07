from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.effects.device import NullKeyboard
from keyrgb.core.effects.engine import EffectsEngine


def _backend_caps(*, per_key: bool = False, hardware_effects: bool = False) -> BackendCapabilities:
    return BackendCapabilities(
        brightness=True,
        per_key=per_key,
        color=True,
        hardware_effects=hardware_effects,
        palette=False,
    )


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


def test_controller_native_wake_handoff_skips_initial_prime(monkeypatch) -> None:
    engine = EffectsEngine()
    engine.backend_caps = _backend_caps(per_key=True)
    engine.kb = NullKeyboard()
    engine.device_available = True
    engine._ensure_device_available = lambda: True  # type: ignore[assignment]
    engine.per_key_colors = {(0, 0): (0, 255, 255)}
    engine.brightness = 40
    engine._device_mode_off = True

    calls: list[str] = []
    monkeypatch.setattr(engine, "_prime_per_key_frame", lambda: calls.append("prime") or True)
    monkeypatch.setattr(engine, "_fade_in_per_key", lambda **_kwargs: calls.append("fade"))

    engine._start_sw_effect(
        target=lambda: None,
        prev_color=(0, 0, 0),
        fade_to_color=(0, 255, 255),
        controller_brightness_handoff=50,
    )

    assert calls == []
    assert engine._device_mode_off is False
    assert engine._last_hw_mode_brightness == 50
    assert engine._last_rendered_brightness == 50
    assert engine._reactive_state._reactive_controller_brightness_handoff_active is True
    engine.stop()


def test_soft_on_start_after_turn_off_primes_with_user_mode_reassert(monkeypatch) -> None:
    """Soft-on starts at brightness=1 after turn_off must still prime.

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
    and the entire fade block is skipped. The test confirms _fade_uniform_color
    and _fade_in_per_key are uncalled during an SW→SW start.
    """

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
