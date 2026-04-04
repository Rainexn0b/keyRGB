from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, TypeAlias

from src.core.effects.reactive._evdev_specs import SPECIAL_KEY_NAMES
from src.core.effects.reactive._evdev_specs import keyboard_control_keys, keyboard_letter_keys
from src.core.resources.layouts import key_id_for_slot_id, slot_id_for_key_id
from src.core.utils.logging_utils import log_throttled

Key = Tuple[int, int]
KeyCells = Tuple[Key, ...]


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

    letter_keys = keyboard_letter_keys(evdev)
    control_keys = keyboard_control_keys(evdev)

    return len(key_codes & letter_keys) >= 8 and len(key_codes & control_keys) >= 3


def evdev_key_name_to_key_id(name: str) -> Optional[str]:
    """Translate evdev key names into legacy calibrated key_id strings.

    This remains as a thin compatibility helper for code paths that still need
    semantic-looking key ids before translating into canonical slot ids.
    """

    if not name:
        return None
    n = str(name).strip().upper()
    if n.startswith("KEY_"):
        n = n[4:]

    if n in SPECIAL_KEY_NAMES:
        return SPECIAL_KEY_NAMES[n]

    if n.startswith("F") and n[1:].isdigit():
        return n.lower()

    if n.startswith("KP") and n[2:].isdigit():
        return f"num{n[2:]}"

    if len(n) == 1 and ("A" <= n <= "Z" or "0" <= n <= "9"):
        return n.lower()

    return None


def evdev_key_name_to_slot_id(name: str, *, physical_layout: str = "auto") -> Optional[str]:
    """Translate evdev key names into canonical physical slot ids when known."""

    key_id = evdev_key_name_to_key_id(name)
    if not key_id:
        return None
    return str(slot_id_for_key_id(physical_layout, key_id) or key_id)


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


def _normalize_key_cells(raw_cells: object) -> KeyCells:
    if isinstance(raw_cells, str):
        if "," not in raw_cells:
            return ()
        row_text, col_text = raw_cells.split(",", 1)
        try:
            return ((int(row_text), int(col_text)),)
        except (TypeError, ValueError):
            return ()

    if isinstance(raw_cells, (list, tuple)) and len(raw_cells) == 2:
        first, second = raw_cells
        if not isinstance(first, (list, tuple, dict)) and not isinstance(second, (list, tuple, dict)):
            try:
                return ((int(first), int(second)),)
            except (TypeError, ValueError):
                return ()

    if not isinstance(raw_cells, (list, tuple)):
        return ()

    out: list[Key] = []
    for cell in raw_cells:
        normalized = _normalize_key_cells(cell)
        if not normalized:
            continue
        key = normalized[0]
        if key not in out:
            out.append(key)
    return tuple(out)


def load_active_profile_slot_keymap() -> Dict[str, KeyCells]:
    try:
        from src.core.profile import profiles
    except ImportError:
        return {}

    try:
        active = profiles.get_active_profile()
        km = profiles.load_keymap(active)
        out: Dict[str, KeyCells] = {}
        for key_id, raw_cells in (km or {}).items():
            cells = list(_normalize_key_cells(raw_cells))
            if cells:
                raw_identity = str(key_id or "").strip()
                if key_id_for_slot_id("auto", raw_identity):
                    normalized_identity = raw_identity.lower()
                else:
                    legacy_identity = evdev_key_name_to_key_id(raw_identity) or raw_identity.lower()
                    normalized_identity = str(slot_id_for_key_id("auto", legacy_identity) or legacy_identity).lower()
                out[normalized_identity] = tuple(cells)
        return out
    except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as exc:
        _log_reactive_input_exception(
            "effects.reactive.profile_keymap_load_failed",
            "Failed to load reactive keymap from active profile",
            exc,
        )
        return {}


def poll_keypress_slot_id(devices: Optional[EvdevKeyboardDevices]) -> Optional[str]:
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
                slot_id = evdev_key_name_to_slot_id(str(name) if name else "")
                if slot_id:
                    return slot_id
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
