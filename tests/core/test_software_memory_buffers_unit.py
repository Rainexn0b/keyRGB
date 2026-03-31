from __future__ import annotations


class _StopAfterFrames:
    def __init__(self, *, frames: int) -> None:
        self.frames_left = int(frames)

    def is_set(self) -> bool:
        return self.frames_left <= 0

    def set(self) -> None:
        self.frames_left = 0

    def wait(self, _dt: float) -> None:
        self.frames_left -= 1


class _UniformOnlyKB:
    def set_color(self, *_args, **_kwargs) -> None:
        return


def _mk_engine(*, current_color=(255, 0, 0), brightness: int = 25, speed: int = 4):
    class E:
        def __init__(self) -> None:
            self.running = True
            self.stop_event = _StopAfterFrames(frames=2)
            self.brightness = brightness
            self.speed = speed
            self.current_color = current_color
            self.per_key_colors = None
            self.kb = _UniformOnlyKB()

    return E()


def test_run_breathing_reuses_frame_map() -> None:
    from src.core.effects.software._effects_basic import run_breathing

    engine = _mk_engine()
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_breathing(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_color_cycle_reuses_frame_map() -> None:
    from src.core.effects.software._effects_basic import run_color_cycle

    engine = _mk_engine()
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_color_cycle(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_strobe_reuses_frame_map() -> None:
    from src.core.effects.software._effects_particles import run_strobe

    engine = _mk_engine()
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_strobe(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_chase_uniform_fallback_reuses_frame_map() -> None:
    from src.core.effects.software._effects_particles import run_chase

    engine = _mk_engine(current_color=(0, 200, 255), speed=8)
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_chase(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_rainbow_wave_reuses_frame_map() -> None:
    from src.core.effects.software._effects_basic import run_rainbow_wave

    engine = _mk_engine(speed=8)
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_rainbow_wave(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_twinkle_reuses_frame_map() -> None:
    from src.core.effects.software._effects_particles import run_twinkle

    engine = _mk_engine(speed=8)
    seen_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        seen_ids.append(id(color_map))

    run_twinkle(engine, render_fn=render_fn)

    assert len(seen_ids) == 2
    assert len(set(seen_ids)) == 1


def test_run_random_reuses_transition_buffers() -> None:
    from src.core.effects.software._effects_basic import run_random

    engine = _mk_engine(speed=8)
    prev_ids: list[int] = []
    target_ids: list[int] = []

    def render_fn(_engine, *, color_map) -> None:
        _ = color_map
        prev_ids.append(id(_engine._sw_random_prev_map))
        target_ids.append(id(_engine._sw_random_target_map))

    run_random(engine, render_fn=render_fn)

    assert len(prev_ids) == 2
    assert len(set(prev_ids)) == 1
    assert len(target_ids) == 2
    assert len(set(target_ids)) == 1
