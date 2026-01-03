from __future__ import annotations

from typing import Dict, Optional, Tuple

Key = Tuple[int, int]


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
        "SYSRQ": "prtsc",
        "PRINT": "prtsc",
        "SCROLLLOCK": "sc",
        "PAUSE": "pause",
        "BREAK": "pause",
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


def try_open_evdev_keyboards() -> Optional[list]:
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


def load_active_profile_keymap() -> Dict[str, Key]:
    try:
        from src.core.profile import profiles

        active = profiles.get_active_profile()
        km = profiles.load_keymap(active)
        return {str(k).lower(): (int(v[0]), int(v[1])) for k, v in (km or {}).items()}
    except Exception:
        return {}


def poll_keypress_key_id(devices: Optional[list]) -> Optional[str]:
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
