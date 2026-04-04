from __future__ import annotations

import logging

from src.core.effects.reactive.render import (
    apply_backdrop_brightness_scale,
    backdrop_brightness_scale_factor,
    pulse_brightness_scale_factor,
    _resolve_brightness,
)


class FakeEngine:
    def __init__(
        self,
        *,
        global_hw=25,
        eff=25,
        base=None,
        per_key_colors=None,
        dim_temp_active: bool = False,
        last_rendered: int = 50,
    ):
        # Global hardware brightness cap (profile/policy).
        self.brightness = global_hw
        # Reactive typing pulse/highlight target brightness.
        self.reactive_brightness = eff
        self.per_key_brightness = base
        # Simulate active per-key colors if dict provided
        self.per_key_colors = per_key_colors
        self._dim_temp_active = dim_temp_active
        # Default to 50 (steady-state running) so the stability guard does
        # not interfere with tests that verify base brightness calculations.
        self._last_rendered_brightness = last_rendered


def test_resolve_brightness() -> None:
    # Case 1: Dim Profile (Global=5, Base=5), Bright Effect (Eff=50)
    # When not temp-dimmed, hardware brightness tracks engine.brightness, NOT the
    # effect level.  hw = max(global_hw=5, base=5) = 5.  The effect (eff=50) does
    # NOT raise the hardware brightness.  Use last_rendered=5 (steady-state) so
    # the stability guard doesn't step down from a prior value.
    engine = FakeEngine(global_hw=5, eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)}, last_rendered=5)
    base, eff, hw = _resolve_brightness(engine)
    assert base == 5
    assert eff == 50
    assert hw == 5

    # Case 2: Bright Profile (Global=50, Base=50), Dim Effect (Eff=5)
    engine = FakeEngine(global_hw=50, eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})
    base, eff, hw = _resolve_brightness(engine)
    assert base == 50
    assert eff == 5
    assert hw == 50

    # Case 3: No backdrop (per_key_colors None)
    # Global should ignore base (base becomes 0).
    # last_rendered=25 keeps the guard from clamping (steady-state assumption).
    engine = FakeEngine(global_hw=25, eff=25, base=50, per_key_colors=None, last_rendered=25)
    base, eff, hw = _resolve_brightness(engine)
    # Base defaults to 0 because per_key_colors is None
    assert base == 0
    assert eff == 25
    assert hw == 25


def test_resolve_brightness_temp_dim_caps_to_profile() -> None:
    # last_rendered=5 represents steady-state temp-dim (guard already converged).
    engine = FakeEngine(
        global_hw=5,
        eff=50,
        base=50,
        per_key_colors={(0, 0): (0, 0, 0)},
        dim_temp_active=True,
        last_rendered=5,
    )
    base, eff, hw = _resolve_brightness(engine)
    assert base == 50
    assert eff == 50
    assert hw == 5


def test_scaling_factors_dim_base_bright_effect() -> None:
    # Not temp-dimmed: hardware brightness tracks engine.brightness (global_hw),
    # NOT the effect level.  hw = max(global_hw=5, base=5) = 5.
    # Use last_rendered=5 (steady-state) so the guard doesn't interfere.
    engine = FakeEngine(global_hw=5, eff=50, base=5, per_key_colors={(0, 0): (0, 0, 0)}, last_rendered=5)

    # Backdrop scale: base >= hw (5 >= 5) => 1.0  (no over-drive compensation needed)
    b_factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=50)
    assert abs(b_factor - 1.0) < 1e-9

    # Pulse scale: eff >= hw (50 >= 5) => 1.0
    p_factor = pulse_brightness_scale_factor(engine)
    assert abs(p_factor - 1.0) < 1e-9


def test_scaling_factors_bright_base_dim_effect() -> None:
    # Base=50, Eff=5, Global=50
    engine = FakeEngine(global_hw=50, eff=5, base=50, per_key_colors={(0, 0): (0, 0, 0)})

    # Backdrop scale: 50/50 = 1.0
    b_factor = backdrop_brightness_scale_factor(engine, effect_brightness_hw=5)
    assert abs(b_factor - 1.0) < 1e-9

    # Pulse scale: 5/50 = 0.1
    p_factor = pulse_brightness_scale_factor(engine)
    assert abs(p_factor - 0.1) < 1e-9


def test_scaling_application() -> None:
    # Test RGB scaling application
    base_unscaled = {(0, 0): (200, 100, 50)}
    factor = 0.1
    base_scaled = apply_backdrop_brightness_scale(base_unscaled, factor=factor)
    assert base_scaled[(0, 0)] == (20, 10, 5)


def test_build_frame_base_maps_reuses_uniform_buffer() -> None:
    from src.core.effects.reactive._base_maps import build_frame_base_maps

    engine = FakeEngine(global_hw=25, eff=25, base=50, per_key_colors=None, last_rendered=25)

    active1, base_unscaled1, base1 = build_frame_base_maps(
        engine,
        background_rgb=(5, 5, 5),
        effect_brightness_hw=25,
        backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
    )
    active2, base_unscaled2, base2 = build_frame_base_maps(
        engine,
        background_rgb=(7, 8, 9),
        effect_brightness_hw=25,
        backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
    )

    assert active1 is False
    assert active2 is False
    assert base_unscaled1 is base1
    assert base_unscaled1 is base_unscaled2
    assert base_unscaled2 is base2
    assert base2[(0, 0)] == (7, 8, 9)


def test_build_frame_base_maps_reuses_per_key_backdrop_buffers() -> None:
    from src.core.effects.reactive._base_maps import build_frame_base_maps

    engine = FakeEngine(
        global_hw=50,
        eff=5,
        base=5,
        per_key_colors={(0, 0): (100, 50, 25)},
        last_rendered=50,
    )

    active1, base_unscaled1, base1 = build_frame_base_maps(
        engine,
        background_rgb=(1, 1, 1),
        effect_brightness_hw=50,
        backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
    )
    engine.per_key_colors = {(0, 0): (20, 40, 60)}
    active2, base_unscaled2, base2 = build_frame_base_maps(
        engine,
        background_rgb=(1, 1, 1),
        effect_brightness_hw=50,
        backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
    )

    assert active1 is True
    assert active2 is True
    assert base_unscaled1 is base_unscaled2
    assert base1 is base2
    assert base1 is not base_unscaled1
    assert base_unscaled2[(0, 0)] == (20, 40, 60)
    assert base2[(0, 0)] == (2, 4, 6)


def test_build_frame_base_maps_skips_scaled_copy_when_factor_is_one() -> None:
    from src.core.effects.reactive._base_maps import build_frame_base_maps

    engine = FakeEngine(
        global_hw=5,
        eff=50,
        base=5,
        per_key_colors={(0, 0): (11, 22, 33)},
        last_rendered=5,
    )

    active, base_unscaled, base = build_frame_base_maps(
        engine,
        background_rgb=(1, 1, 1),
        effect_brightness_hw=5,
        backdrop_brightness_scale_factor_fn=backdrop_brightness_scale_factor,
    )

    assert active is True
    assert base is base_unscaled
    assert base[(0, 0)] == (11, 22, 33)


def test_get_engine_color_map_buffer_bypasses_hostile_engine_attribute_lookup() -> None:
    from src.core.effects.reactive._base_maps import get_engine_color_map_buffer

    class _HostileEngine:
        def __getattribute__(self, name: str):
            if name == "_reactive_base_unscaled_map":
                raise RuntimeError("hostile attribute lookup")
            return object.__getattribute__(self, name)

    engine = _HostileEngine()

    first = get_engine_color_map_buffer(engine, "_reactive_base_unscaled_map")
    second = get_engine_color_map_buffer(engine, "_reactive_base_unscaled_map")

    assert first == {}
    assert second is first
    assert vars(engine)["_reactive_base_unscaled_map"] is first


def test_get_engine_color_map_buffer_degrades_when_engine_cannot_store_buffers() -> None:
    from src.core.effects.reactive._base_maps import get_engine_color_map_buffer

    class _SlotOnlyEngine:
        __slots__ = ()

    engine = _SlotOnlyEngine()

    first = get_engine_color_map_buffer(engine, "_reactive_base_unscaled_map")
    second = get_engine_color_map_buffer(engine, "_reactive_base_unscaled_map")

    assert first == {}
    assert second == {}
    assert second is not first


def test_fill_per_key_backdrop_map_accepts_duck_typed_items_objects() -> None:
    from src.core.effects.reactive._base_maps import fill_per_key_backdrop_map

    class _DuckTypedPerKeyColors:
        def items(self):
            return [
                ((0, 0), (9, 8, 7)),
                (("1", "2"), ("3", "4", "5")),
            ]

    dest = {(9, 9): (1, 1, 1)}

    result = fill_per_key_backdrop_map(
        dest,
        base_color=(2, 3, 4),
        per_key_colors=_DuckTypedPerKeyColors(),
    )

    assert result is dest
    assert dest[(0, 0)] == (9, 8, 7)
    assert dest[(1, 2)] == (3, 4, 5)
    assert dest[(0, 1)] == (2, 3, 4)
    assert (9, 9) not in dest


def test_fill_per_key_backdrop_map_logs_once_and_preserves_uniform_base_on_broken_items_iteration(
    caplog,
    monkeypatch,
) -> None:
    from src.core.effects.reactive._base_maps import fill_per_key_backdrop_map
    from src.core.utils import logging_utils

    class _BrokenItems:
        def items(self):
            class _BrokenIterable:
                def __iter__(self):
                    return self

                def __next__(self):
                    raise RuntimeError("broken mapping iteration")

            return _BrokenIterable()

    logging_utils._last_log_times.clear()
    monkeypatch.setattr(logging_utils.time, "monotonic", iter((100.0, 100.1)).__next__)

    first_dest = {(9, 9): (1, 1, 1)}
    second_dest = {(8, 8): (2, 2, 2)}

    with caplog.at_level(logging.ERROR, logger="src.core.effects.reactive._base_maps"):
        first_result = fill_per_key_backdrop_map(
            first_dest,
            base_color=(3, 4, 5),
            per_key_colors=_BrokenItems(),
        )
        second_result = fill_per_key_backdrop_map(
            second_dest,
            base_color=(6, 7, 8),
            per_key_colors=_BrokenItems(),
        )

    assert first_result is first_dest
    assert second_result is second_dest
    assert first_dest[(0, 0)] == (3, 4, 5)
    assert second_dest[(0, 0)] == (6, 7, 8)
    assert (9, 9) not in first_dest
    assert (8, 8) not in second_dest

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "Failed to iterate reactive per-key backdrop colors"
    ]
    assert len(records) == 1
    assert records[0].exc_info is not None

    logging_utils._last_log_times.clear()
