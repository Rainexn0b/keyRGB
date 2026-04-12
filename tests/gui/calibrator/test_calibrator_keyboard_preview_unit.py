from __future__ import annotations

import logging

import pytest

import src.gui.calibrator.helpers.keyboard_preview as keyboard_preview
from src.gui.calibrator.helpers.keyboard_preview import KeyboardPreviewSession, _full_black_map


class _FakeConfig:
    def __init__(
        self,
        *,
        effect: str = "rainbow",
        speed: int = 5,
        brightness: int = 25,
        color: tuple[int, int, int] | list[int] = (255, 0, 0),
        per_key_colors: dict[tuple[int, int], tuple[int, int, int]] | object | None = None,
    ) -> None:
        self.effect = effect
        self.speed = speed
        self.brightness = brightness
        self.color = color
        self.per_key_colors = per_key_colors if per_key_colors is not None else {}


class _BrokenCopyMap:
    def __iter__(self):
        raise RuntimeError("copy failed")


class _UnexpectedCopyMap:
    def __iter__(self):
        raise AssertionError("unexpected copy bug")


class _SetAttrFailConfig:
    def __init__(self, *, fail_key: str) -> None:
        object.__setattr__(self, "_fail_key", fail_key)
        object.__setattr__(self, "_history", [])
        object.__setattr__(self, "effect", "wave")
        object.__setattr__(self, "speed", 9)
        object.__setattr__(self, "brightness", 80)
        object.__setattr__(self, "color", (4, 5, 6))
        object.__setattr__(self, "per_key_colors", {(0, 0): (7, 8, 9)})

    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        self._history.append((name, value))
        if name == self._fail_key:
            raise RuntimeError(f"cannot set {name}")
        object.__setattr__(self, name, value)


class _UnexpectedSetAttrFailConfig(_SetAttrFailConfig):
    def __setattr__(self, name: str, value) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return

        self._history.append((name, value))
        if name == self._fail_key:
            raise AssertionError(f"unexpected setattr bug: {name}")
        object.__setattr__(self, name, value)


def test_full_black_map_covers_each_cell_with_black() -> None:
    assert _full_black_map(rows=2, cols=3) == {
        (0, 0): (0, 0, 0),
        (0, 1): (0, 0, 0),
        (0, 2): (0, 0, 0),
        (1, 0): (0, 0, 0),
        (1, 1): (0, 0, 0),
        (1, 2): (0, 0, 0),
    }


def test_post_init_snapshots_original_config_values() -> None:
    cfg = _FakeConfig(
        effect="static",
        speed=7,
        brightness=33,
        color=[1, 2, 3],
        per_key_colors={(0, 0): (10, 11, 12)},
    )

    session = KeyboardPreviewSession(cfg=cfg, rows=3, cols=4)
    cfg.effect = "perkey"
    cfg.speed = 1
    cfg.brightness = 99
    cfg.color = (9, 9, 9)
    cfg.per_key_colors[(0, 1)] = (20, 21, 22)

    assert session._orig_effect == "static"
    assert session._orig_speed == 7
    assert session._orig_brightness == 33
    assert session._orig_color == (1, 2, 3)
    assert session._orig_per_key_colors == {(0, 0): (10, 11, 12)}


def test_post_init_logs_and_uses_empty_map_when_per_key_colors_copy_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_log_throttled(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(keyboard_preview, "log_throttled", fake_log_throttled)
    cfg = _FakeConfig(per_key_colors=_BrokenCopyMap())

    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)

    assert session._orig_per_key_colors == {}
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[1] == "calibrator.preview.orig_per_key_colors"
    assert kwargs["level"] == logging.DEBUG
    assert kwargs["msg"] == "Failed to snapshot per_key_colors; will restore empty map"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_post_init_propagates_unexpected_per_key_colors_copy_failures() -> None:
    cfg = _FakeConfig(per_key_colors=_UnexpectedCopyMap())

    with pytest.raises(AssertionError, match="unexpected copy bug"):
        KeyboardPreviewSession(cfg=cfg, rows=2, cols=2)


@pytest.mark.parametrize(
    ("starting_brightness", "expected_brightness"),
    [(-5, 50), (0, 50), (12, 12)],
)
def test_apply_probe_cell_updates_preview_and_only_forces_non_positive_brightness(
    starting_brightness: int,
    expected_brightness: int,
) -> None:
    cfg = _FakeConfig(brightness=starting_brightness)
    session = KeyboardPreviewSession(cfg=cfg, rows=2, cols=3)

    session.apply_probe_cell(1, 2)

    assert cfg.effect == "perkey"
    assert cfg.brightness == expected_brightness
    assert cfg.per_key_colors == {
        (0, 0): (0, 0, 0),
        (0, 1): (0, 0, 0),
        (0, 2): (0, 0, 0),
        (1, 0): (0, 0, 0),
        (1, 1): (0, 0, 0),
        (1, 2): (255, 255, 255),
    }


def test_restore_continues_after_setattr_failure_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_log_throttled(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(keyboard_preview, "log_throttled", fake_log_throttled)
    cfg = _SetAttrFailConfig(fail_key="color")
    session = KeyboardPreviewSession(cfg=cfg, rows=1, cols=1)

    object.__setattr__(cfg, "effect", "perkey")
    object.__setattr__(cfg, "speed", 1)
    object.__setattr__(cfg, "brightness", 0)
    object.__setattr__(cfg, "color", (99, 99, 99))
    object.__setattr__(cfg, "per_key_colors", {(0, 0): (255, 255, 255)})

    session.restore()

    assert [name for name, _ in cfg._history] == [
        "per_key_colors",
        "color",
        "speed",
        "brightness",
        "effect",
    ]
    assert cfg.per_key_colors == {(0, 0): (7, 8, 9)}
    assert cfg.color == (99, 99, 99)
    assert cfg.speed == 9
    assert cfg.brightness == 80
    assert cfg.effect == "wave"
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[1] == "calibrator.preview.restore.color"
    assert kwargs["level"] == logging.DEBUG
    assert kwargs["msg"] == "Failed to restore config field: color"
    assert isinstance(kwargs["exc"], RuntimeError)


def test_restore_propagates_unexpected_setattr_failures() -> None:
    cfg = _UnexpectedSetAttrFailConfig(fail_key="color")
    session = KeyboardPreviewSession(cfg=cfg, rows=1, cols=1)

    object.__setattr__(cfg, "effect", "perkey")
    object.__setattr__(cfg, "speed", 1)
    object.__setattr__(cfg, "brightness", 0)
    object.__setattr__(cfg, "color", (99, 99, 99))
    object.__setattr__(cfg, "per_key_colors", {(0, 0): (255, 255, 255)})

    with pytest.raises(AssertionError, match="unexpected setattr bug: color"):
        session.restore()
