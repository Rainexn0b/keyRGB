from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

from keyrgb.core.effects.software import base as sw_base


class _ReentrantCallbackLock:
    """RLock that fires ``on_acquire`` on the first real lock acquisition.

    Used to reproduce the KSW-3 interleaving deterministically: a software
    worker passes its loop stop-check, then blocks on ``kb_lock`` while a
    concurrent turn-off latches ``_device_mode_off``. The callback emulates the
    latched mode-off becoming visible exactly while the worker holds the lock.
    """

    def __init__(self, *, on_acquire=None):
        self._lock = RLock()
        self.on_acquire = on_acquire

    def __enter__(self):
        self._lock.acquire()
        if self.on_acquire is not None:
            self.on_acquire()

    def __exit__(self, exc_type, exc, tb):
        self._lock.release()
        return False


class _DummyLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _PerKeyKB:
    def __init__(self, *, per_key_mode_policy: str = "init_once"):
        self.calls: list[tuple[str, int]] = []
        self.keyrgb_per_key_mode_policy = str(per_key_mode_policy)

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        del save
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        self.calls.append(("set_brightness", int(brightness)))

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = False):
        assert enable_user_mode is False
        self.calls.append(("set_key_colors", int(brightness)))


class _UniformKB:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def enable_user_mode(self, *, brightness: int, save: bool = False):
        del save
        self.calls.append(("enable_user_mode", int(brightness)))

    def set_brightness(self, brightness: int):
        self.calls.append(("set_brightness", int(brightness)))

    def set_color(self, _color, *, brightness: int):
        self.calls.append(("set_color", int(brightness)))


class _SecondaryKB:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def set_color(self, _color, *, brightness: int):
        self.calls.append(("set_color", int(brightness)))


def _mk_engine(
    *,
    per_key: bool,
    brightness: int = 25,
    device_mode_off: bool = False,
    running: bool = True,
    lock=None,
    secondary=None,
):
    kb = _PerKeyKB() if per_key else _UniformKB()
    ns = {
        "backend_caps": SimpleNamespace(per_key=per_key),
        "kb": kb,
        "kb_lock": lock or _DummyLock(),
        "brightness": brightness,
        "speed": 4,
        "current_color": (255, 0, 0),
        "per_key_colors": {(0, 0): (255, 255, 255)} if per_key else None,
        "mark_device_unavailable": lambda: None,
        "_last_hw_mode_brightness": None,
        "_device_mode_off": device_mode_off,
        "running": running,
    }
    if secondary is not None:
        ns["secondary_software_targets_provider"] = lambda: [secondary]
        ns["software_effect_target"] = "all_uniform_capable"
    return SimpleNamespace(**ns)


# --- KSW-3: post-off software frame commit ---------------------------------


def test_sw_render_per_key_skips_all_output_when_device_mode_off() -> None:
    secondary = _SecondaryKB()
    engine = _mk_engine(per_key=True, device_mode_off=True, secondary=secondary)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == []
    assert secondary.calls == []


def test_sw_render_uniform_skips_all_output_when_device_mode_off() -> None:
    secondary = _SecondaryKB()
    engine = _mk_engine(per_key=False, device_mode_off=True, secondary=secondary)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == []
    assert secondary.calls == []


def test_sw_render_per_key_skips_when_mode_off_latched_after_lock_acquire() -> None:
    """Reproduce the exact KSW-3 interleaving.

    The worker passes its loop stop-check, then acquires ``kb_lock``; a
    concurrent turn-off latches ``_device_mode_off`` while the worker holds the
    lock. The locked-boundary guard must suppress the write.
    """

    engine = _mk_engine(per_key=True, device_mode_off=False)

    def on_acquire() -> None:
        engine._device_mode_off = True

    engine.kb_lock = _ReentrantCallbackLock(on_acquire=on_acquire)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == []
    assert engine._device_mode_off is True


def test_sw_render_uniform_skips_when_mode_off_latched_after_lock_acquire() -> None:
    engine = _mk_engine(per_key=False, device_mode_off=False)

    def on_acquire() -> None:
        engine._device_mode_off = True

    engine.kb_lock = _ReentrantCallbackLock(on_acquire=on_acquire)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == []
    assert engine._device_mode_off is True


def test_sw_render_per_key_skips_when_running_cleared_without_mode_off() -> None:
    """The guard also honors a cleared ``running`` flag (turn_off stops the worker)."""

    engine = _mk_engine(per_key=True, device_mode_off=False, running=False)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == []


def test_sw_render_per_key_still_writes_when_mode_on() -> None:
    """Normal rendering must remain intact: mode-on + running writes a frame."""

    engine = _mk_engine(per_key=True, device_mode_off=False, running=True)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 25),
        ("set_key_colors", 25),
    ]


def test_sw_render_uniform_still_writes_when_mode_on() -> None:
    engine = _mk_engine(per_key=False, device_mode_off=False, running=True)

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 25),
        ("set_color", 25),
    ]


def test_sw_render_per_key_writes_when_mode_off_attr_absent() -> None:
    """Legacy engines without ``_device_mode_off`` still render (defensive default)."""

    engine = _mk_engine(per_key=True, device_mode_off=False)
    del engine._device_mode_off

    sw_base.render(engine, color_map={(0, 0): (255, 0, 0)})

    assert engine.kb.calls == [
        ("enable_user_mode", 25),
        ("set_key_colors", 25),
    ]
