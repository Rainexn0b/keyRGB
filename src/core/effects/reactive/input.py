from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TypeAlias

from src.core.utils.logging_utils import log_throttled

Key = Tuple[int, int]


EvdevKeyboardDevice: TypeAlias = Any
EvdevKeyboardDevices: TypeAlias = list[EvdevKeyboardDevice]


logger = logging.getLogger(__name__)


def _log_reactive_input_exception(key: str, message: str, exc: BaseException) -> None:
    log_throttled(
        logger,
        key,
        interval_s=30,
        level=logging.WARNING,
        msg=message,
        exc=exc,
    )


def _close_evdev_device(dev: EvdevKeyboardDevice, *, log_key: str, message: str) -> None:
    close_fn = getattr(dev, "close", None)
    if not callable(close_fn):
        return

    try:
        close_fn()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _log_reactive_input_exception(log_key, message, exc)


def _drop_evdev_device(devices: EvdevKeyboardDevices, dev: EvdevKeyboardDevice) -> None:
    try:
        devices.remove(dev)
    except ValueError:
        pass

    _close_evdev_device(
        dev,
        log_key="effects.reactive.evdev.close_failed",
        message="Failed to close evdev keyboard device",
    )


def _read_udev_input_properties(device_path: str) -> Dict[str, str]:
    try:
        stat_result = os.stat(device_path)
        major_num = os.major(stat_result.st_rdev)
        minor_num = os.minor(stat_result.st_rdev)
        data_path = Path(f"/run/udev/data/c{major_num}:{minor_num}")
        if not data_path.is_file():
            return {}
        props: Dict[str, str] = {}
        for line in data_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("E:"):
                continue
            key, sep, value = line[2:].partition("=")
            if sep:
                props[key] = value.strip()
        return props
    except (OSError, ValueError):
        return {}


def _udev_device_is_keyboard(device_path: str) -> Optional[bool]:
    props = _read_udev_input_properties(device_path)
    if not props:
        return None
    return props.get("ID_INPUT_KEYBOARD") == "1"


def _evdev_device_looks_like_keyboard(dev: EvdevKeyboardDevice, evdev: Any) -> bool:
    try:
        caps = dev.capabilities(verbose=False)
        key_codes = set(caps.get(evdev.ecodes.EV_KEY, []) or [])
    except (AttributeError, OSError, TypeError, ValueError):
        return False

    letter_keys = {
        evdev.ecodes.KEY_A,
        evdev.ecodes.KEY_B,
        evdev.ecodes.KEY_C,
        evdev.ecodes.KEY_D,
        evdev.ecodes.KEY_E,
        evdev.ecodes.KEY_F,
        evdev.ecodes.KEY_G,
        evdev.ecodes.KEY_H,
        evdev.ecodes.KEY_I,
        evdev.ecodes.KEY_J,
        evdev.ecodes.KEY_K,
        evdev.ecodes.KEY_L,
        evdev.ecodes.KEY_M,
        evdev.ecodes.KEY_N,
        evdev.ecodes.KEY_O,
        evdev.ecodes.KEY_P,
        evdev.ecodes.KEY_Q,
        evdev.ecodes.KEY_R,
        evdev.ecodes.KEY_S,
        evdev.ecodes.KEY_T,
        evdev.ecodes.KEY_U,
        evdev.ecodes.KEY_V,
        evdev.ecodes.KEY_W,
        evdev.ecodes.KEY_X,
        evdev.ecodes.KEY_Y,
        evdev.ecodes.KEY_Z,
    }
    control_keys = {
        evdev.ecodes.KEY_SPACE,
        evdev.ecodes.KEY_ENTER,
        evdev.ecodes.KEY_TAB,
        evdev.ecodes.KEY_BACKSPACE,
        evdev.ecodes.KEY_LEFTSHIFT,
        evdev.ecodes.KEY_RIGHTSHIFT,
    }

    return len(key_codes & letter_keys) >= 8 and len(key_codes & control_keys) >= 3


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
        "102ND": "nonusbackslash",
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


def try_open_evdev_keyboards() -> Optional[EvdevKeyboardDevices]:
    if str(os.environ.get("KEYRGB_DISABLE_EVDEV", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return None

    try:
        import evdev  # type: ignore
    except ImportError:
        return None

    try:
        device_paths = list(evdev.list_devices())
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        _log_reactive_input_exception(
            "effects.reactive.evdev.list_devices_failed",
            "Failed to enumerate evdev devices for reactive input",
            exc,
        )
        return None

    out = []
    for device_path in device_paths:
        keyboard_tag = _udev_device_is_keyboard(device_path)
        if keyboard_tag is False:
            continue

        try:
            dev = evdev.InputDevice(device_path)
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            _log_reactive_input_exception(
                "effects.reactive.evdev.open_failed",
                f"Failed to open evdev device {device_path!r} for reactive input",
                exc,
            )
            continue

        if keyboard_tag is True or _evdev_device_looks_like_keyboard(dev, evdev):
            out.append(dev)
            continue

        _close_evdev_device(
            dev,
            log_key="effects.reactive.evdev.close_non_keyboard_failed",
            message="Failed to close non-keyboard evdev device",
        )

    return out or None


def close_evdev_keyboards(devices: Optional[EvdevKeyboardDevices]) -> None:
    if not devices:
        return

    for dev in list(devices):
        _close_evdev_device(
            dev,
            log_key="effects.reactive.evdev.close_failed",
            message="Failed to close evdev keyboard device",
        )

    devices.clear()


def reactive_synthetic_fallback_enabled() -> bool:
    raw = str(os.environ.get("KEYRGB_REACTIVE_SYNTHETIC_FALLBACK", "")).strip().lower()

    return raw in {"1", "true", "yes", "on"}


def load_active_profile_keymap() -> Dict[str, Key]:
    try:
        from src.core.profile import profiles
    except ImportError:
        return {}

    try:
        active = profiles.get_active_profile()
        km = profiles.load_keymap(active)
        return {str(k).lower(): (int(v[0]), int(v[1])) for k, v in (km or {}).items()}
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as exc:
        _log_reactive_input_exception(
            "effects.reactive.profile_keymap_load_failed",
            "Failed to load reactive keymap from active profile",
            exc,
        )
        return {}


def poll_keypress_key_id(devices: Optional[EvdevKeyboardDevices]) -> Optional[str]:
    if not devices:
        return None

    try:
        import select
    except ImportError:
        return None

    try:
        import evdev  # type: ignore
    except ImportError:
        return None

    try:
        r, _, _ = select.select(devices, [], [], 0)
    except (OSError, TypeError, ValueError) as exc:
        _log_reactive_input_exception(
            "effects.reactive.evdev.select_failed",
            "Reactive evdev polling failed; closing keyboard devices",
            exc,
        )
        close_evdev_keyboards(devices)
        return None

    if not r:
        return None

    for dev in list(r):
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
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            dev_name = getattr(dev, "path", "<unknown>")
            _log_reactive_input_exception(
                "effects.reactive.evdev.read_failed",
                f"Reactive evdev device read failed for {dev_name}; dropping device",
                exc,
            )
            _drop_evdev_device(devices, dev)
            continue

    return None
