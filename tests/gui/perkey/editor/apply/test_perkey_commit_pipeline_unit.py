from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.gui.perkey.commit_pipeline import PerKeyCommitPipeline


@dataclass
class DummyConfig:
    brightness: int = 0
    effect: str | None = None
    per_key_colors: dict[tuple[int, int], tuple[int, int, int]] | None = None


def test_commit_pipeline_throttles_unless_forced() -> None:
    calls: list[dict[str, object]] = []

    def push_fn(kb, colors, *, brightness: int, enable_user_mode: bool = True):
        calls.append(
            {
                "kb": kb,
                "colors": dict(colors),
                "brightness": brightness,
                "enable_user_mode": enable_user_mode,
            }
        )
        return kb

    t = 1000.0

    def time_fn() -> float:
        return t

    cfg = DummyConfig(brightness=50)
    pipeline = PerKeyCommitPipeline(commit_interval_s=1.0)
    pipeline._time_fn = time_fn  # deterministic time

    kb = object()
    colors = {(0, 0): (1, 2, 3)}

    kb2, colors2 = pipeline.commit(
        kb=kb,
        colors=dict(colors),
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(9, 9, 9),
        fallback_color=(8, 8, 8),
        push_fn=push_fn,
        force=False,
    )
    assert kb2 is kb
    assert colors2 == {(0, 0): (1, 2, 3)}
    assert len(calls) == 1

    # Same timestamp => should throttle
    kb3, colors3 = pipeline.commit(
        kb=kb,
        colors=dict(colors),
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(9, 9, 9),
        fallback_color=(8, 8, 8),
        push_fn=push_fn,
        force=False,
    )
    assert kb3 is kb
    assert colors3 == {(0, 0): (1, 2, 3)}
    assert len(calls) == 1

    # Forced commit bypasses throttling
    kb4, _ = pipeline.commit(
        kb=kb,
        colors=dict(colors),
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(9, 9, 9),
        fallback_color=(8, 8, 8),
        push_fn=push_fn,
        force=True,
    )
    assert kb4 is kb
    assert len(calls) == 2


def test_commit_pipeline_sets_brightness_when_zero() -> None:
    calls: list[int] = []

    def push_fn(kb, colors, *, brightness: int, enable_user_mode: bool = True):
        calls.append(brightness)
        return kb

    cfg = DummyConfig(brightness=0)
    pipeline = PerKeyCommitPipeline(commit_interval_s=0.0)

    kb = object()
    kb2, colors2 = pipeline.commit(
        kb=kb,
        colors={(0, 0): (0, 0, 0)},
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(7, 7, 7),
        fallback_color=(8, 8, 8),
        push_fn=push_fn,
        force=True,
    )

    assert kb2 is kb
    assert cfg.brightness == 25
    assert cfg.effect == "perkey"
    assert cfg.per_key_colors == colors2
    assert calls == [25]


@dataclass
class _SelectiveWriteFailConfig:
    brightness: int = 0
    effect: str | None = None
    per_key_colors: dict[tuple[int, int], tuple[int, int, int]] | None = None
    fail_fields: tuple[str, ...] = ()
    write_history: list[str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "write_history", [])

    def __setattr__(self, name: str, value) -> None:
        if name in {"fail_fields", "write_history"}:
            object.__setattr__(self, name, value)
            return
        history = self.__dict__.get("write_history")
        if history is not None:
            history.append(name)
        if name in self.fail_fields:
            raise RuntimeError(f"cannot set {name}")
        object.__setattr__(self, name, value)


def test_commit_pipeline_keeps_pushing_when_brightness_write_fails() -> None:
    push_calls: list[dict[str, object]] = []

    def push_fn(kb, colors, *, brightness: int, enable_user_mode: bool = True):
        push_calls.append(
            {
                "kb": kb,
                "colors": dict(colors),
                "brightness": brightness,
                "enable_user_mode": enable_user_mode,
            }
        )
        return kb

    cfg = _SelectiveWriteFailConfig(brightness=0, fail_fields=("brightness",))
    pipeline = PerKeyCommitPipeline(commit_interval_s=0.0)

    kb = object()
    _kb2, full = pipeline.commit(
        kb=kb,
        colors={(0, 0): (1, 2, 3)},
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(7, 7, 7),
        fallback_color=(8, 8, 8),
        push_fn=push_fn,
        force=True,
    )

    assert cfg.write_history == ["brightness", "effect", "per_key_colors"]
    assert cfg.brightness == 0
    assert cfg.effect == "perkey"
    assert cfg.per_key_colors == full
    assert push_calls == [{"kb": kb, "colors": full, "brightness": 0, "enable_user_mode": True}]


def test_commit_pipeline_still_updates_colors_when_effect_write_fails() -> None:
    cfg = _SelectiveWriteFailConfig(brightness=10, fail_fields=("effect",))
    pipeline = PerKeyCommitPipeline(commit_interval_s=0.0)

    kb = object()
    kb2, full = pipeline.commit(
        kb=kb,
        colors={(0, 0): (4, 5, 6)},
        config=cfg,
        num_rows=1,
        num_cols=1,
        base_color=(7, 7, 7),
        fallback_color=(8, 8, 8),
        push_fn=lambda current_kb, _colors, *, brightness, enable_user_mode: (current_kb, brightness, enable_user_mode),
        force=True,
    )

    assert cfg.write_history == ["effect", "per_key_colors"]
    assert cfg.effect is None
    assert cfg.per_key_colors == full
    assert kb2 == (kb, 10, True)


def test_commit_pipeline_ensures_full_map_uses_fallback_when_base_black() -> None:
    calls: list[dict[tuple[int, int], tuple[int, int, int]]] = []

    def push_fn(kb, colors, *, brightness: int, enable_user_mode: bool = True):
        calls.append(dict(colors))
        return kb

    cfg = DummyConfig(brightness=10)
    pipeline = PerKeyCommitPipeline(commit_interval_s=0.0)

    kb = object()
    _kb2, full = pipeline.commit(
        kb=kb,
        colors={},
        config=cfg,
        num_rows=1,
        num_cols=2,
        base_color=(0, 0, 0),
        fallback_color=(3, 4, 5),
        push_fn=push_fn,
        force=True,
    )

    assert full == {(0, 0): (3, 4, 5), (0, 1): (3, 4, 5)}
    assert calls and calls[-1] == full


@dataclass
class _UnexpectedWriteFailConfig:
    brightness: int = 0
    effect: str | None = None
    per_key_colors: dict[tuple[int, int], tuple[int, int, int]] | None = None
    fail_fields: tuple[str, ...] = ()

    def __setattr__(self, name: str, value) -> None:
        if name == "fail_fields":
            object.__setattr__(self, name, value)
            return
        if name in self.fail_fields:
            raise AssertionError(f"unexpected write failure: {name}")
        object.__setattr__(self, name, value)


def test_commit_pipeline_propagates_unexpected_config_write_failures() -> None:
    cfg = _UnexpectedWriteFailConfig(brightness=10, fail_fields=("effect",))
    pipeline = PerKeyCommitPipeline(commit_interval_s=0.0)

    with pytest.raises(AssertionError, match="unexpected write failure: effect"):
        pipeline.commit(
            kb=object(),
            colors={(0, 0): (4, 5, 6)},
            config=cfg,
            num_rows=1,
            num_cols=1,
            base_color=(7, 7, 7),
            fallback_color=(8, 8, 8),
            push_fn=lambda current_kb, _colors, *, brightness, enable_user_mode: current_kb,
            force=True,
        )
