from __future__ import annotations

import logging
from threading import RLock
from types import SimpleNamespace

import pytest

from src.core.effects.software import base as software_base
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_KEYBOARD
from src.core.effects.software_targets import normalize_software_effect_target
from src.core.effects.software_targets import render_secondary_uniform_rgb
from src.core.effects.software_targets import software_render_targets


class _SpyKeyboard:
    def __init__(self) -> None:
        self.per_key_calls: list[tuple[dict[tuple[int, int], tuple[int, int, int]], int]] = []

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = False) -> None:
        self.per_key_calls.append((dict(color_map), int(brightness)))


class _SpySecondaryTarget:
    key = "lightbar:048d:7001"
    device_type = "lightbar"
    supports_per_key = False

    def __init__(self) -> None:
        self.color_calls: list[tuple[tuple[int, int, int], int]] = []

    @property
    def device(self):
        return self

    def set_color(self, color, *, brightness: int) -> None:
        self.color_calls.append((tuple(color), int(brightness)))


class _PermissionDeniedSecondaryTarget(_SpySecondaryTarget):
    def set_color(self, color, *, brightness: int) -> None:
        raise PermissionError("secondary denied")


class _RecoverableFailingSecondaryTarget(_SpySecondaryTarget):
    def set_color(self, color, *, brightness: int) -> None:
        del color, brightness
        raise RuntimeError("secondary failed")


class _UnexpectedFailingSecondaryTarget(_SpySecondaryTarget):
    def set_color(self, color, *, brightness: int) -> None:
        del color, brightness
        raise AssertionError("unexpected secondary bug")


def test_normalize_software_effect_target_defaults_to_keyboard() -> None:
    assert normalize_software_effect_target(None) == SOFTWARE_EFFECT_TARGET_KEYBOARD
    assert normalize_software_effect_target(object()) == SOFTWARE_EFFECT_TARGET_KEYBOARD
    assert normalize_software_effect_target("ALL_UNIFORM_CAPABLE") == SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    assert normalize_software_effect_target("nope") == SOFTWARE_EFFECT_TARGET_KEYBOARD


def test_software_render_targets_include_auxiliary_targets_only_when_enabled() -> None:
    secondary = _SpySecondaryTarget()
    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_KEYBOARD,
        secondary_software_targets_provider=lambda: [secondary],
    )

    keyboard_only = software_render_targets(engine)
    assert [target.key for target in keyboard_only] == ["keyboard"]

    engine.software_effect_target = SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    with_aux = software_render_targets(engine)
    assert [target.key for target in with_aux] == ["keyboard", "lightbar:048d:7001"]


def test_software_render_targets_fall_back_to_keyboard_when_provider_raises() -> None:
    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: (_ for _ in ()).throw(RuntimeError("provider boom")),
    )

    assert [target.key for target in software_render_targets(engine)] == ["keyboard"]


def test_software_render_targets_propagate_unexpected_provider_failures() -> None:
    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: (_ for _ in ()).throw(AssertionError("unexpected provider bug")),
    )

    with pytest.raises(AssertionError, match="unexpected provider bug"):
        software_render_targets(engine)


def test_software_render_fans_out_uniformized_frame_to_auxiliary_targets() -> None:
    keyboard = _SpyKeyboard()
    secondary = _SpySecondaryTarget()
    engine = SimpleNamespace(
        kb=keyboard,
        kb_lock=RLock(),
        brightness=25,
        _last_hw_mode_brightness=None,
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: [secondary],
        mark_device_unavailable=lambda: None,
    )

    software_base.render(
        engine,
        color_map={
            (0, 0): (10, 20, 30),
            (0, 1): (30, 40, 50),
        },
    )

    assert keyboard.per_key_calls == [({(0, 0): (10, 20, 30), (0, 1): (30, 40, 50)}, 25)]
    assert secondary.color_calls == [((20, 30, 40), 25)]


def test_render_secondary_uniform_rgb_keeps_permission_callback_failures_non_fatal(monkeypatch) -> None:
    secondary = _PermissionDeniedSecondaryTarget()
    logged_messages: list[str] = []

    def capture_log(*args, **kwargs) -> None:
        logged_messages.append(kwargs["msg"])

    monkeypatch.setattr("src.core.effects.software_targets.log_throttled", capture_log)

    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: [secondary],
        _permission_error_cb=lambda exc: (_ for _ in ()).throw(RuntimeError("callback boom")),
    )

    render_secondary_uniform_rgb(
        engine,
        rgb=(10, 20, 30),
        brightness_hw=25,
        logger=logging.getLogger("test.software_targets"),
        log_key="software-test",
    )

    assert logged_messages == [
        "Secondary software-effect permission callback failed for lightbar:048d:7001",
        "Secondary software-effect render failed for lightbar:048d:7001",
    ]


def test_render_secondary_uniform_rgb_propagates_unexpected_permission_callback_failures(monkeypatch) -> None:
    secondary = _PermissionDeniedSecondaryTarget()

    monkeypatch.setattr("src.core.effects.software_targets.log_throttled", lambda *args, **kwargs: None)

    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: [secondary],
        _permission_error_cb=lambda exc: (_ for _ in ()).throw(AssertionError("unexpected callback bug")),
    )

    with pytest.raises(AssertionError, match="unexpected callback bug"):
        render_secondary_uniform_rgb(
            engine,
            rgb=(10, 20, 30),
            brightness_hw=25,
            logger=logging.getLogger("test.software_targets"),
            log_key="software-test",
        )


def test_render_secondary_uniform_rgb_logs_recoverable_target_failures(monkeypatch) -> None:
    secondary = _RecoverableFailingSecondaryTarget()
    logged_messages: list[str] = []

    def capture_log(*args, **kwargs) -> None:
        logged_messages.append(kwargs["msg"])

    monkeypatch.setattr("src.core.effects.software_targets.log_throttled", capture_log)

    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: [secondary],
        _permission_error_cb=lambda exc: None,
    )

    render_secondary_uniform_rgb(
        engine,
        rgb=(10, 20, 30),
        brightness_hw=25,
        logger=logging.getLogger("test.software_targets"),
        log_key="software-test",
    )

    assert logged_messages == ["Secondary software-effect render failed for lightbar:048d:7001"]


def test_render_secondary_uniform_rgb_propagates_unexpected_target_failures(monkeypatch) -> None:
    secondary = _UnexpectedFailingSecondaryTarget()

    monkeypatch.setattr("src.core.effects.software_targets.log_throttled", lambda *args, **kwargs: None)

    engine = SimpleNamespace(
        kb=_SpyKeyboard(),
        software_effect_target=SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
        secondary_software_targets_provider=lambda: [secondary],
        _permission_error_cb=lambda exc: None,
    )

    with pytest.raises(AssertionError, match="unexpected secondary bug"):
        render_secondary_uniform_rgb(
            engine,
            rgb=(10, 20, 30),
            brightness_hw=25,
            logger=logging.getLogger("test.software_targets"),
            log_key="software-test",
        )
