from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def run_reactive_fade_loop(engine: "EffectsEngine", *, api: Any) -> None:
    dt = api.frame_dt_s()

    press = api.create_press_source(
        engine,
        press_source_cls=api._PressSource,
        open_keyboards=api.try_open_evdev_keyboards,
        synthetic_fallback_enabled=api.reactive_synthetic_fallback_enabled,
    )
    slot_keymap = api.load_slot_keymap(loader=api.load_active_profile_slot_keymap)

    pulses: list[api._Pulse] = []
    try:
        while engine.running and not engine.stop_event.is_set():
            p = api.pace(engine)
            press.spawn_interval_s = max(0.10, 0.45 / max(0.1, p))
            try:
                eff_hw = int(getattr(engine, "reactive_brightness", 0) or 0)
            except (TypeError, ValueError):
                eff_hw = 0

            react_color = api.get_engine_reactive_color(engine)
            manual = api.get_engine_manual_reactive_color(engine)

            pressed_slot_id = press.poll_slot_id(dt=dt)
            if pressed_slot_id is not None:
                mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)

                ttl = 0.48 / p
                if mapped_cells:
                    for row, col in mapped_cells:
                        pulses.append(api._Pulse(row=int(row), col=int(col), age_s=0.0, ttl_s=ttl))
                else:
                    row = api.random.randrange(api.NUM_ROWS)
                    col = api.random.randrange(api.NUM_COLS)
                    pulses.append(api._Pulse(row=row, col=col, age_s=0.0, ttl_s=ttl))

            pulses = api._age_pulses_in_place(pulses, dt=dt)

            overlay = api.get_engine_overlay_buffer(engine, "_reactive_fade_overlay")
            api.build_fade_overlay_into(overlay, pulses)

            try:
                target_mix = max((float(value) for value in overlay.values()), default=0.0)
            except (TypeError, ValueError):
                target_mix = 0.0
            api._set_reactive_active_pulse_mix(engine, target=target_mix)

            per_key_backdrop_active, base_unscaled, base = api.build_frame_base_maps(
                engine,
                background_rgb=api.scale(react_color, 0.06),
                effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0),
                backdrop_brightness_scale_factor_fn=api.backdrop_brightness_scale_factor,
            )

            if eff_hw <= 0:
                api._set_reactive_active_pulse_mix(engine, target=0.0)
                api.render(engine, color_map=base)
                engine.stop_event.wait(dt)
                continue

            pulse_scale = api.pulse_brightness_scale_factor(engine)

            if not bool(getattr(engine.kb, "set_key_colors", None)):
                w_global = 0.0
                if overlay:
                    try:
                        w_global = max(float(value) for value in overlay.values())
                    except (TypeError, ValueError):
                        w_global = 0.0

                try:
                    base_rgb = next(iter(base.values()))
                except StopIteration:
                    base_rgb = (0, 0, 0)
                try:
                    base_rgb_unscaled = next(iter(base_unscaled.values()))
                except StopIteration:
                    base_rgb_unscaled = base_rgb

                if manual is not None:
                    pulse_rgb = react_color
                elif per_key_backdrop_active:
                    pulse_rgb = api._brightness_boost_pulse(base_rgb=base_rgb_unscaled)
                else:
                    pulse_rgb = api._pick_contrasting_highlight(
                        base_rgb=base_rgb_unscaled,
                        preferred_rgb=react_color,
                    )

                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                rgb = api.mix(base_rgb, pulse_rgb, t=min(1.0, w_global))
                api._render_uniform_fallback(engine, rgb=rgb)
                engine.stop_event.wait(dt)
                continue

            color_map = api.get_engine_color_map_buffer(engine, "_reactive_fade_frame_map")
            color_map.clear()
            for key, base_rgb in base.items():
                base_rgb_unscaled = base_unscaled.get(key, base_rgb)
                weight = overlay.get(key, 0.0)
                if manual is not None:
                    pulse_rgb = react_color
                elif per_key_backdrop_active:
                    pulse_rgb = api._brightness_boost_pulse(base_rgb=base_rgb_unscaled)
                else:
                    pulse_rgb = api._pick_contrasting_highlight(
                        base_rgb=base_rgb_unscaled,
                        preferred_rgb=react_color,
                    )

                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                color_map[key] = api.mix(base_rgb, pulse_rgb, t=min(1.0, weight))

            api.render(engine, color_map=color_map)
            engine.stop_event.wait(dt)
    finally:
        press.close()
