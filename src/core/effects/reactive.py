from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from src.core.effects.colors import hsv_to_rgb
from src.core.effects.ite_backend import NUM_COLS, NUM_ROWS
from src.core.effects.perkey_animation import build_full_color_grid, enable_user_mode_once
from src.core.effects.transitions import avoid_full_black
from src.core.logging_utils import log_throttled

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine

Color = Tuple[int, int, int]
Key = Tuple[int, int]


def _clamp01(x: float) -> float:
    return 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else x)


def _mix(a: Color, b: Color, t: float) -> Color:
    tt = _clamp01(t)
    return (
        int(round(a[0] + (b[0] - a[0]) * tt)),
        int(round(a[1] + (b[1] - a[1]) * tt)),
        int(round(a[2] + (b[2] - a[2]) * tt)),
    )


def _scale(rgb: Color, s: float) -> Color:
    ss = _clamp01(s)
    return (int(round(rgb[0] * ss)), int(round(rgb[1] * ss)), int(round(rgb[2] * ss)))


def _frame_dt_s() -> float:
    return 1.0 / 60.0


def _pace(engine: "EffectsEngine", *, min_factor: float = 0.8, max_factor: float = 2.2) -> float:
    """Map UI speed (0..10) to an effect pace multiplier.

    Kept consistent with the software effect loops (quadratic curve so speed=10
    is *much* faster).
    """

    try:
        s = int(getattr(engine, "speed", 4) or 0)
    except Exception:
        s = 4
    s = max(0, min(10, s))
    t = float(s) / 10.0
    t = t * t
    min_factor = float(min_factor)
    max_factor = float(max_factor)
    if min_factor == 0.8 and max_factor == 2.2:
        min_factor = 0.25
        max_factor = 10.0
    return float(min_factor + (max_factor - min_factor) * t)


def _has_per_key(engine: "EffectsEngine") -> bool:
    return bool(getattr(engine.kb, "set_key_colors", None))


def _base_color_map(engine: "EffectsEngine") -> Dict[Key, Color]:
    base_color_src = getattr(engine, "current_color", None) or (255, 0, 0)
    base_color = (int(base_color_src[0]), int(base_color_src[1]), int(base_color_src[2]))

    per_key = getattr(engine, "per_key_colors", None) or None
    if not per_key:
        return {(r, c): base_color for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    full = build_full_color_grid(
        base_color=base_color,
        per_key_colors=per_key,
        num_rows=NUM_ROWS,
        num_cols=NUM_COLS,
    )
    return {(r, c): tuple(map(int, rgb)) for (r, c), rgb in full.items()}


def _render(engine: "EffectsEngine", *, color_map: Dict[Key, Color]) -> None:
    if _has_per_key(engine):
        try:
            enable_user_mode_once(kb=engine.kb, kb_lock=engine.kb_lock, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_key_colors(color_map, brightness=int(engine.brightness), enable_user_mode=False)
            return
        except Exception as exc:
            log_throttled(
                logger,
                "effects.render.per_key_failed",
                interval_s=30,
                level=logging.WARNING,
                msg="Per-key render failed; falling back to uniform",
                exc=exc,
            )

    # Uniform fallback: average the map to a single color.
    if not color_map:
        rgb = (0, 0, 0)
    else:
        rs = sum(c[0] for c in color_map.values())
        gs = sum(c[1] for c in color_map.values())
        bs = sum(c[2] for c in color_map.values())
        n = max(1, len(color_map))
        rgb = (int(rs / n), int(gs / n), int(bs / n))

    r, g, b = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
    with engine.kb_lock:
        engine.kb.set_color((r, g, b), brightness=int(engine.brightness))


# =====================
# evdev mapping helpers
# =====================

def evdev_key_name_to_key_id(name: str) -> Optional[str]:
    """Translate evdev key names (e.g. KEY_A) into our calibrated key_id strings."""

    if not name:
        return None
    n = str(name).strip().upper()
    if n.startswith("KEY_"):
        n = n[4:]

    special = {
        "ESC": "esc",
        "GRAVE": "grave",
        "MINUS": "minus",
        "EQUAL": "equal",
        "BACKSPACE": "backspace",
        "TAB": "tab",
        "CAPSLOCK": "caps",
        "ENTER": "enter",
        "SPACE": "space",
        "LEFTSHIFT": "lshift",
        "RIGHTSHIFT": "rshift",
        "LEFTCTRL": "lctrl",
        "RIGHTCTRL": "rctrl",
        "LEFTALT": "lalt",
        "RIGHTALT": "ralt",
        "LEFTMETA": "lwin",
        "RIGHTMETA": "rwin",
        "COMPOSE": "menu",
        "MENU": "menu",
        "BACKSLASH": "bslash",
        "LEFTBRACE": "lbracket",
        "RIGHTBRACE": "rbracket",
        "SEMICOLON": "semicolon",
        "APOSTROPHE": "quote",
        "COMMA": "comma",
        "DOT": "dot",
        "SLASH": "slash",
        "DELETE": "del",
        "INSERT": "ins",
        "HOME": "home",
        "END": "end",
        "PAGEUP": "pgup",
        "PAGEDOWN": "pgdn",
        "UP": "up",
        "DOWN": "down",
        "LEFT": "left",
        "RIGHT": "right",
        "NUMLOCK": "numlock",
        "KPSLASH": "numslash",
        "KPASTERISK": "numstar",
        "KPMINUS": "numminus",
        "KPPLUS": "numplus",
        "KPENTER": "numenter",
        "KPDOT": "numdot",
        # Additional special keys
        "SYSRQ": "prtsc",
        "PRINT": "prtsc",
        "SCROLLLOCK": "sc",
        "PAUSE": "pause",
        "BREAK": "pause",
        # Media keys (may vary by keyboard)
        "VOLUMEUP": "volup",
        "VOLUMEDOWN": "voldown",
        "MUTE": "mute",
        "PLAYPAUSE": "play",
        "PLAY": "play",
        "STOP": "stop",
        "NEXTSONG": "next",
        "PREVIOUSSONG": "prev",
        "CALC": "calc",
        "MAIL": "mail",
        "WWW": "www",
        "HOMEPAGE": "home",
        "BACK": "back",
        "FORWARD": "forward",
    }

    if n in special:
        return special[n]

    if n.startswith("F") and n[1:].isdigit():
        return n.lower()

    if n.startswith("KP") and n[2:].isdigit():
        return f"num{n[2:]}"

    if len(n) == 1 and ("A" <= n <= "Z" or "0" <= n <= "9"):
        return n.lower()

    return None


def _try_open_evdev_keyboards() -> Optional[list]:
    try:
        import os

        if str(os.environ.get("KEYRGB_DISABLE_EVDEV", "")).strip().lower() in {"1", "true", "yes"}:
            return None
    except Exception:
        pass

    try:
        import evdev  # type: ignore
    except Exception:
        return None

    try:
        devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
    except Exception:
        return None

    out = []
    for dev in devices:
        try:
            caps = dev.capabilities(verbose=False)
            if evdev.ecodes.EV_KEY in caps:
                dev.grab = getattr(dev, "grab", None)
                out.append(dev)
        except Exception:
            continue

    return out or None


def _load_active_profile_keymap() -> Dict[str, Key]:
    try:
        from src.core.profile import profiles

        active = profiles.get_active_profile()
        km = profiles.load_keymap(active)
        return {str(k).lower(): (int(v[0]), int(v[1])) for k, v in (km or {}).items()}
    except Exception:
        return {}


def _poll_keypress_key_id(devices: Optional[list]) -> Optional[str]:
    if not devices:
        return None
    try:
        import select
        import evdev  # type: ignore

        r, _, _ = select.select(devices, [], [], 0)
        if not r:
            return None
        for dev in r:
            try:
                for event in dev.read():
                    if getattr(event, "type", None) != evdev.ecodes.EV_KEY:
                        continue
                    if getattr(event, "value", None) != 1:
                        continue
                    code = getattr(event, "code", None)
                    if code is None:
                        continue
                    name = evdev.ecodes.KEY.get(int(code))
                    key_id = evdev_key_name_to_key_id(str(name) if name else "")
                    if key_id:
                        return key_id
            except Exception:
                continue
    except Exception:
        return None
    return None


# =====================
# Reactive effects
# =====================


@dataclass
class _Pulse:
    row: int
    col: int
    age_s: float
    ttl_s: float


def _reactive_loop(engine: "EffectsEngine", *, mode: str) -> None:
    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    react_color_src = getattr(engine, "current_color", None) or (255, 255, 255)
    react_color = (int(react_color_src[0]), int(react_color_src[1]), int(react_color_src[2]))

    if not (getattr(engine, "per_key_colors", None) or None):
        background = _scale(react_color, 0.06)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = _try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, pace))

    keymap = _load_active_profile_keymap()

    pulses: List[_Pulse] = []
    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = _poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            ttl = 0.40 / pace
            pulses.append(_Pulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl))

        new_pulses: List[_Pulse] = []
        for p in pulses:
            p.age_s += dt
            if p.age_s <= p.ttl_s:
                new_pulses.append(p)
        pulses = new_pulses

        overlay: Dict[Key, float] = {}
        for p in pulses:
            if mode == "fade":
                intensity = 1.0 - (p.age_s / p.ttl_s)
                overlay[(p.row, p.col)] = max(overlay.get((p.row, p.col), 0.0), intensity)
                continue

            intensity = 1.0 - (p.age_s / p.ttl_s)
            radius = int(round(1 + 5 * (p.age_s / p.ttl_s)))
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    r = p.row + dr
                    c = p.col + dc
                    if r < 0 or r >= NUM_ROWS or c < 0 or c >= NUM_COLS:
                        continue
                    d = abs(dr) + abs(dc)
                    if d > radius:
                        continue
                    w = max(0.0, intensity * (1.0 - (d / max(1.0, float(radius)))))
                    k = (r, c)
                    overlay[k] = max(overlay.get(k, 0.0), w)

        if not _has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            rgb = _mix(avg_base, react_color, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = _mix(base_rgb, react_color, t=min(1.0, w))

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)


def run_reactive_fade(engine: "EffectsEngine") -> None:
    _reactive_loop(engine, mode="fade")


def run_reactive_ripple(engine: "EffectsEngine") -> None:
    _reactive_loop(engine, mode="ripple")


def run_reactive_rainbow(engine: "EffectsEngine") -> None:
    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    if not (getattr(engine, "per_key_colors", None) or None):
        background = (5, 5, 5)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = _try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, pace))
    keymap = _load_active_profile_keymap()

    @dataclass
    class _RainbowPulse:
        row: int
        col: int
        age_s: float
        ttl_s: float
        hue_offset: float

    pulses: List[_RainbowPulse] = []
    global_hue = 0.0

    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = _poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            ttl = 0.50 / pace
            pulses.append(_RainbowPulse(row=rr, col=cc, age_s=0.0, ttl_s=ttl, hue_offset=global_hue))

        new_pulses: List[_RainbowPulse] = []
        for p in pulses:
            p.age_s += dt
            if p.age_s <= p.ttl_s:
                new_pulses.append(p)
        pulses = new_pulses

        overlay: Dict[Key, Tuple[float, float]] = {}
        for p in pulses:
            intensity = 1.0 - (p.age_s / p.ttl_s)
            hue = (p.hue_offset + (p.age_s / p.ttl_s) * 360.0) % 360.0
            radius = int(round(1 + 3 * (p.age_s / p.ttl_s)))
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    r = p.row + dr
                    c = p.col + dc
                    if r < 0 or r >= NUM_ROWS or c < 0 or c >= NUM_COLS:
                        continue
                    d = abs(dr) + abs(dc)
                    if d > radius:
                        continue
                    w = max(0.0, intensity * (1.0 - (d / max(1.0, float(radius)))))
                    k = (r, c)
                    if k not in overlay or w > overlay[k][0]:
                        overlay[k] = (w, hue)

        if not _has_per_key(engine):
            global_w = max((v[0] for v in overlay.values()), default=0.0)
            avg_hue = sum(v[1] for v in overlay.values()) / max(1, len(overlay)) if overlay else 0.0
            rgb = hsv_to_rgb(avg_hue, 1.0, global_w)
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            global_hue = (global_hue + 2.0 * pace) % 360.0
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            if k in overlay:
                w, hue = overlay[k]
                pulse_rgb = hsv_to_rgb(hue, 1.0, 1.0)
                color_map[k] = _mix(base_rgb, pulse_rgb, t=min(1.0, w))
            else:
                color_map[k] = base_rgb

        _render(engine, color_map=color_map)
        global_hue = (global_hue + 2.0 * pace) % 360.0
        engine.stop_event.wait(dt)


def run_reactive_snake(engine: "EffectsEngine") -> None:
    base = _base_color_map(engine)
    dt = _frame_dt_s()
    pace = _pace(engine)

    react_color_src = getattr(engine, "current_color", None) or (0, 255, 255)
    react_color = (int(react_color_src[0]), int(react_color_src[1]), int(react_color_src[2]))

    if not (getattr(engine, "per_key_colors", None) or None):
        background = _scale(react_color, 0.08)
        base = {(r, c): background for r in range(NUM_ROWS) for c in range(NUM_COLS)}

    devices = _try_open_evdev_keyboards()
    synthetic = not devices
    spawn_acc = 0.0
    spawn_interval_s = max(0.10, 0.45 / max(0.1, pace))
    keymap = _load_active_profile_keymap()

    @dataclass
    class _SnakeSegment:
        row: int
        col: int
        age_s: float

    trail: List[_SnakeSegment] = []
    max_trail_len = 12
    segment_ttl_s = 1.2 / pace

    while engine.running and not engine.stop_event.is_set():
        pressed_key_id = _poll_keypress_key_id(devices)
        pressed = bool(pressed_key_id)

        if synthetic:
            spawn_acc += dt
            if spawn_acc >= spawn_interval_s:
                spawn_acc = 0.0
                pressed = True

        if pressed:
            if pressed_key_id:
                rc = keymap.get(str(pressed_key_id).lower())
            else:
                rc = None

            if rc is not None:
                rr, cc = int(rc[0]), int(rc[1])
            else:
                rr = random.randrange(NUM_ROWS)
                cc = random.randrange(NUM_COLS)

            trail.append(_SnakeSegment(row=rr, col=cc, age_s=0.0))
            if len(trail) > max_trail_len:
                trail.pop(0)

        new_trail: List[_SnakeSegment] = []
        for seg in trail:
            seg.age_s += dt
            if seg.age_s <= segment_ttl_s:
                new_trail.append(seg)
        trail = new_trail

        overlay: Dict[Key, float] = {}
        for idx, seg in enumerate(trail):
            position_factor = (idx + 1) / max(1, len(trail))
            age_factor = 1.0 - (seg.age_s / segment_ttl_s)
            intensity = position_factor * age_factor
            k = (seg.row, seg.col)
            overlay[k] = max(overlay.get(k, 0.0), intensity)

        if not _has_per_key(engine):
            global_w = max(overlay.values(), default=0.0)
            rs = sum(c[0] for c in base.values())
            gs = sum(c[1] for c in base.values())
            bs = sum(c[2] for c in base.values())
            n = max(1, len(base))
            avg_base = (int(rs / n), int(gs / n), int(bs / n))
            rgb = _mix(avg_base, react_color, t=min(1.0, global_w))
            rgb = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(engine.brightness))
            with engine.kb_lock:
                engine.kb.set_color(rgb, brightness=int(engine.brightness))
            engine.stop_event.wait(dt)
            continue

        color_map: Dict[Key, Color] = {}
        for k, base_rgb in base.items():
            w = overlay.get(k, 0.0)
            color_map[k] = _mix(base_rgb, react_color, t=min(1.0, w))

        _render(engine, color_map=color_map)
        engine.stop_event.wait(dt)
