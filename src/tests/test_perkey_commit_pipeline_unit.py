from __future__ import annotations

from dataclasses import dataclass

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
