from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from src.core.effects.perkey_animation import load_per_key_colors_from_config
from src.core.effects.perkey_animation import enable_user_mode_once
from src.core.effects.perkey_animation import restore_hidden_per_key_rows_once


def test_load_per_key_colors_from_config_returns_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Config:
        def __init__(self) -> None:
            self.per_key_colors = {(0, 0): (1, 2, 3)}

    monkeypatch.setitem(sys.modules, "src.core.config", SimpleNamespace(Config=_Config))

    assert load_per_key_colors_from_config() == {(0, 0): (1, 2, 3)}


def test_load_per_key_colors_from_config_falls_back_on_runtime_config_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Config:
        @property
        def per_key_colors(self):
            raise ValueError("bad persisted colors")

    monkeypatch.setitem(sys.modules, "src.core.config", SimpleNamespace(Config=_Config))

    assert load_per_key_colors_from_config() == {}


def test_load_per_key_colors_from_config_propagates_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Config:
        @property
        def per_key_colors(self):
            raise AssertionError("unexpected config bug")

    monkeypatch.setitem(sys.modules, "src.core.config", SimpleNamespace(Config=_Config))

    with pytest.raises(AssertionError, match="unexpected config bug"):
        load_per_key_colors_from_config()


def test_enable_user_mode_once_logs_recoverable_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.core.effects.perkey_animation as perkey_animation

    seen: dict[str, object] = {}

    class _Kb:
        def enable_user_mode(self, *, brightness: int, save: bool = False):
            del brightness, save
            raise RuntimeError("user mode failed")

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_log_throttled(logger, key: str, *, interval_s: float, level: int, msg: str, exc=None) -> bool:
        seen.update(key=key, interval_s=interval_s, level=level, msg=msg, exc=exc)
        return True

    monkeypatch.setattr(perkey_animation, "log_throttled", fake_log_throttled)

    enable_user_mode_once(kb=_Kb(), kb_lock=_Lock(), brightness=25)

    assert seen["key"] == "perkey_animation.enable_user_mode_once"
    assert seen["interval_s"] == 120
    assert seen["msg"] == "Failed to enable per-key user mode"
    assert str(seen["exc"]) == "user mode failed"


def test_enable_user_mode_once_propagates_unexpected_errors() -> None:
    class _Kb:
        def enable_user_mode(self, *, brightness: int, save: bool = False):
            del brightness, save
            raise AssertionError("unexpected user mode bug")

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    with pytest.raises(AssertionError, match="unexpected user mode bug"):
        enable_user_mode_once(kb=_Kb(), kb_lock=_Lock(), brightness=25)


def test_enable_user_mode_once_passes_save_flag() -> None:
    seen: list[tuple[int, bool]] = []

    class _Kb:
        def enable_user_mode(self, *, brightness: int, save: bool = False):
            seen.append((int(brightness), bool(save)))

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    enable_user_mode_once(kb=_Kb(), kb_lock=_Lock(), brightness=25, save=True)

    assert seen == [(25, True)]


def test_restore_hidden_per_key_rows_once_rewrites_rows_before_brightness_raise() -> None:
    seen: list[tuple[str, object]] = []

    class _Kb:
        def get_brightness(self) -> int:
            return 0

        def is_off(self) -> bool:
            return False

        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True) -> None:
            seen.append(("rows", (dict(color_map), int(brightness), bool(enable_user_mode))))

        def set_brightness(self, brightness: int) -> None:
            seen.append(("brightness", int(brightness)))

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    handled = restore_hidden_per_key_rows_once(
        kb=_Kb(),
        kb_lock=_Lock(),
        color_map={(0, 0): (1, 2, 3)},
        brightness=25,
    )

    assert handled is True
    assert seen == [
        ("rows", ({(0, 0): (1, 2, 3)}, 25, False)),
        ("brightness", 25),
    ]


def test_restore_hidden_per_key_rows_once_skips_when_device_is_truly_off() -> None:
    class _Kb:
        def get_brightness(self) -> int:
            return 0

        def is_off(self) -> bool:
            return True

        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True) -> None:
            raise AssertionError("should not write rows")

        def set_brightness(self, brightness: int) -> None:
            raise AssertionError("should not restore brightness")

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    handled = restore_hidden_per_key_rows_once(
        kb=_Kb(),
        kb_lock=_Lock(),
        color_map={(0, 0): (1, 2, 3)},
        brightness=25,
    )

    assert handled is False


def test_restore_hidden_per_key_rows_once_uses_known_hardware_hints() -> None:
    seen: list[tuple[str, object]] = []

    class _Kb:
        def get_brightness(self) -> int:
            raise AssertionError("should use known brightness hint")

        def is_off(self) -> bool:
            raise AssertionError("should use known off hint")

        def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True) -> None:
            seen.append(("rows", (dict(color_map), int(brightness), bool(enable_user_mode))))

        def set_brightness(self, brightness: int) -> None:
            seen.append(("brightness", int(brightness)))

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    handled = restore_hidden_per_key_rows_once(
        kb=_Kb(),
        kb_lock=_Lock(),
        color_map={(0, 0): (1, 2, 3)},
        brightness=25,
        known_brightness=0,
        known_is_off=False,
    )

    assert handled is True
    assert seen == [
        ("rows", ({(0, 0): (1, 2, 3)}, 25, False)),
        ("brightness", 25),
    ]
