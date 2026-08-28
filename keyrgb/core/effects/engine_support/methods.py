from __future__ import annotations

from ..fades import fade_in_per_key, fade_uniform_color, prime_per_key_frame
from ..timing import clamped_interval, get_interval


def get_interval_method(self, base_ms: int) -> float:
    return get_interval(base_ms, speed=int(self.speed))


def clamped_interval_method(self, base_ms: int, *, min_s: float) -> float:
    return clamped_interval(base_ms, speed=int(self.speed), min_s=float(min_s))


def fade_uniform_color_method(
    self,
    *,
    from_color: tuple,
    to_color: tuple,
    brightness: int,
    duration_s: float,
    steps: int = 18,
) -> None:
    fade_uniform_color(
        kb=self.kb,
        kb_lock=self.kb_lock,
        from_color=from_color,
        to_color=to_color,
        brightness=brightness,
        duration_s=duration_s,
        steps=steps,
    )


def fade_in_per_key_method(self, *, duration_s: float, steps: int = 12) -> None:
    from keyrgb.core.effects.matrix_layout import geometry_for_engine

    geometry = geometry_for_engine(self)
    fade_in_per_key(
        kb=self.kb,
        kb_lock=self.kb_lock,
        per_key_colors=self.per_key_colors,
        current_color=self.current_color,
        brightness=int(self.brightness),
        duration_s=duration_s,
        steps=steps,
        num_rows=int(geometry.rows),
        num_cols=int(geometry.cols),
    )


def prime_per_key_frame_method(self) -> bool:
    # Soft-on starts at brightness 1 after idle/menu/controller-sleep restore.
    # Firmware sleep leaves is_off=False with brightness=0, so _device_mode_off
    # alone is not always set yet — treat soft-on as requiring user-mode
    # reassert the same way an explicit turn_off does.
    from keyrgb.core.effects.matrix_layout import geometry_for_engine

    start_brightness = int(self.brightness)
    reassert = bool(self._device_mode_off) or start_brightness <= 1
    geometry = geometry_for_engine(self)
    return prime_per_key_frame(
        kb=self.kb,
        kb_lock=self.kb_lock,
        per_key_colors=self.per_key_colors,
        current_color=self.current_color,
        brightness=start_brightness,
        reassert_user_mode=reassert,
        num_rows=int(geometry.rows),
        num_cols=int(geometry.cols),
    )
