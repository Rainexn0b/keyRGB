from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


def run_reactive_ripple_loop(engine: "EffectsEngine", *, api: Any) -> None:
    dt = api.frame_dt_s()

    press = api.create_press_source(
        engine,
        press_source_cls=api._PressSource,
        open_keyboards=api.try_open_evdev_keyboards,
        synthetic_fallback_enabled=api.reactive_synthetic_fallback_enabled,
    )
    slot_keymap = api.load_slot_keymap(loader=api.load_active_profile_slot_keymap)

    pulses: list[api._RainbowPulse] = []
    global_hue = 0.0

    try:
        while engine.running and not engine.stop_event.is_set():
            p = api.pace(engine)
            press.spawn_interval_s = max(0.10, 0.45 / max(0.1, p))
            try:
                eff_hw = int(getattr(engine, "reactive_brightness", 0) or 0)
            except (TypeError, ValueError):
                eff_hw = 0

            per_key_backdrop_active, base_unscaled, base = api.build_frame_base_maps(
                engine,
                background_rgb=(5, 5, 5),
                effect_brightness_hw=int(getattr(engine, "brightness", 25) or 0),
                backdrop_brightness_scale_factor_fn=api.backdrop_brightness_scale_factor,
            )

            if eff_hw <= 0:
                api._set_reactive_active_pulse_mix(engine, target=0.0)
                api.render(engine, color_map=base)
                engine.stop_event.wait(dt)
                continue

            pressed_slot_id = press.poll_slot_id(dt=dt)
            if pressed_slot_id is not None:
                mapped_cells = api.mapped_slot_cells(slot_keymap, pressed_slot_id)

                ttl = 0.65 / p
                if mapped_cells:
                    for row, col in mapped_cells:
                        pulses.append(
                            api._RainbowPulse(
                                row=int(row),
                                col=int(col),
                                age_s=0.0,
                                ttl_s=ttl,
                                hue_offset=global_hue,
                            )
                        )
                else:
                    row = api.random.randrange(api.NUM_ROWS)
                    col = api.random.randrange(api.NUM_COLS)
                    pulses.append(api._RainbowPulse(row=row, col=col, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

            pulses = api._age_pulses_in_place(pulses, dt=dt)

            band = 2.15
            overlay = api.get_engine_overlay_buffer(engine, "_reactive_ripple_overlay")
            api.build_ripple_overlay_into(overlay, pulses, band=band)

            try:
                target_mix = max((float(weight) for (weight, _hue) in overlay.values()), default=0.0)
            except (TypeError, ValueError):
                target_mix = 0.0
            api._set_reactive_active_pulse_mix(engine, target=target_mix)

            manual = api.get_engine_manual_reactive_color(engine)
            pulse_scale = api.pulse_brightness_scale_factor(engine)

            if not bool(getattr(engine.kb, "set_key_colors", None)):
                best_weight = 0.0
                best_hue = 0.0
                for weight, hue in overlay.values():
                    if float(weight) > float(best_weight):
                        best_weight = float(weight)
                        best_hue = float(hue)

                if base:
                    red = sum(color[0] for color in base.values())
                    green = sum(color[1] for color in base.values())
                    blue = sum(color[2] for color in base.values())
                    count = max(1, len(base))
                    base_rgb = (int(red / count), int(green / count), int(blue / count))
                else:
                    base_rgb = (0, 0, 0)

                if manual is not None:
                    pulse_rgb = manual
                else:
                    pulse_rgb = api.hsv_to_rgb(best_hue / 360.0, 1.0, 1.0)

                if pulse_scale < 0.999:
                    pulse_rgb = api.scale(pulse_rgb, pulse_scale)

                rgb = api.mix(base_rgb, pulse_rgb, t=min(1.0, best_weight))
                api._render_uniform_fallback(engine, rgb=rgb)
                global_hue = (global_hue + 2.0 * p) % 360.0
                engine.stop_event.wait(dt)
                continue

            color_map = api.get_engine_color_map_buffer(engine, "_reactive_ripple_frame_map")
            api.build_ripple_color_map_into(
                color_map,
                base=base,
                base_unscaled=base_unscaled,
                overlay=overlay,
                per_key_backdrop_active=per_key_backdrop_active,
                manual=manual,
                pulse_scale=pulse_scale,
            )

            api.render(engine, color_map=color_map)
            global_hue = (global_hue + 2.0 * p) % 360.0
            engine.stop_event.wait(dt)
    finally:
        press.close()
