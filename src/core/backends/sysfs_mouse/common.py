from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.backends.sysfs.common import _leds_root

_NOISY_TOKENS = (
    "capslock",
    "numlock",
    "scrolllock",
    "micmute",
    "mute",
    "kbd",
    "keyboard",
    "lightbar",
    "battery",
    "charging",
    "power",
    "wlan",
    "rfkill",
    "tpacpi",
)
_MOUSE_TOKENS = ("mouse", "pointer")
_VENDOR_TOKENS = (
    "logitech",
    "razer",
    "steelseries",
    "corsair",
    "roccat",
    "glorious",
    "hyperx",
    "pulsar",
    "lamzu",
    "zowie",
    "finalmouse",
    "endgame",
)
_MOUSE_ZONE_TOKENS = ("scroll", "scrollwheel", "wheel", "dpi")
_WEAK_ZONE_TOKENS = ("logo",)


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip().lower()
    except (OSError, UnicodeDecodeError):
        return ""


def _device_metadata_text(led_dir: Path) -> str:
    parts: list[str] = []
    device_dir = led_dir / "device"
    if not device_dir.exists():
        return ""

    for candidate in (device_dir / "name", device_dir / "modalias"):
        value = _safe_read_text(candidate)
        if value:
            parts.append(value)

    try:
        for child in device_dir.iterdir():
            if not child.is_dir() or not child.name.startswith("input"):
                continue
            value = _safe_read_text(child / "name")
            if value:
                parts.append(value)
    except OSError:
        pass

    return " ".join(parts)


def _contains_any_token(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _matching_tokens(text: str, tokens: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(token for token in tokens if token in text)


def inspect_led_candidate(led_dir: Path) -> dict[str, Any]:
    name = str(led_dir.name or "").strip().lower()
    metadata = _device_metadata_text(led_dir)
    combined = f"{name} {metadata}".strip()

    noisy_tokens = _matching_tokens(combined, _NOISY_TOKENS)
    mouse_tokens = _matching_tokens(combined, _MOUSE_TOKENS)
    metadata_mouse_tokens = _matching_tokens(metadata, _MOUSE_TOKENS)
    vendor_tokens = _matching_tokens(combined, _VENDOR_TOKENS)
    strong_zone_tokens = _matching_tokens(name, _MOUSE_ZONE_TOKENS)
    weak_zone_tokens = _matching_tokens(name, _WEAK_ZONE_TOKENS)

    matched = False
    match_reason = ""
    if noisy_tokens:
        match_reason = f"excluded by noisy token(s): {', '.join(noisy_tokens)}"
    elif mouse_tokens:
        matched = True
        match_reason = f"mouse evidence from name/metadata: {', '.join(mouse_tokens)}"
    elif vendor_tokens and strong_zone_tokens:
        matched = True
        match_reason = (
            "vendor mouse-zone evidence: "
            f"vendor={', '.join(vendor_tokens)} zone={', '.join(strong_zone_tokens)}"
        )
    elif vendor_tokens and weak_zone_tokens and metadata_mouse_tokens:
        matched = True
        match_reason = (
            "vendor logo LED confirmed by mouse metadata: "
            f"vendor={', '.join(vendor_tokens)} metadata={', '.join(metadata_mouse_tokens)}"
        )
    else:
        match_reason = "no mouse/pointer evidence in LED name or device metadata"

    brightness_path = led_dir / "brightness"
    max_brightness_path = led_dir / "max_brightness"
    has_brightness = brightness_path.exists()
    has_max_brightness = max_brightness_path.exists()
    color_capable = _is_color_capable_led(led_dir)
    brightness_readable = os.access(brightness_path, os.R_OK) if has_brightness else False
    brightness_writable = os.access(brightness_path, os.W_OK) if has_brightness else False

    eligible = bool(matched and has_brightness and has_max_brightness and color_capable)
    reasons: list[str] = [match_reason]
    if matched and not has_brightness:
        reasons.append("missing brightness node")
    if matched and not has_max_brightness:
        reasons.append("missing max_brightness node")
    if matched and not color_capable:
        reasons.append("no writable color-capable sysfs attributes")

    score = 0
    try:
        score = int(_score_led_dir(led_dir)) if matched else 0
    except (OSError, TypeError, ValueError):
        score = 0

    return {
        "name": led_dir.name,
        "path": str(led_dir),
        "metadata": metadata,
        "matched": matched,
        "eligible": eligible,
        "score": score,
        "reasons": reasons,
        "has_brightness": has_brightness,
        "has_max_brightness": has_max_brightness,
        "color_capable": color_capable,
        "brightness_readable": brightness_readable,
        "brightness_writable": brightness_writable,
        "vendor_tokens": list(vendor_tokens),
        "mouse_tokens": list(mouse_tokens),
    }


def _is_candidate_led(name: str, *, led_dir: Path | None = None) -> bool:
    if led_dir is None:
        return False
    return bool(inspect_led_candidate(led_dir).get("matched"))


def _is_color_capable_led(led_dir: Path) -> bool:
    return any(
        (
            (led_dir / "multi_intensity").exists(),
            (led_dir / "color").exists(),
            (led_dir / "rgb").exists(),
            (led_dir / "color_left").exists(),
            (led_dir / "color_center").exists(),
            (led_dir / "color_right").exists(),
            (led_dir / "color_extra").exists(),
        )
    )


def _score_led_dir(led_dir: Path) -> int:
    name = led_dir.name.lower()
    metadata = _device_metadata_text(led_dir)
    combined = f"{name} {metadata}".strip()
    score = 0

    if _contains_any_token(combined, _MOUSE_TOKENS):
        score += 40
    if _contains_any_token(combined, _VENDOR_TOKENS):
        score += 10
    if "rgb" in name:
        score += 10
    if "logo" in name:
        score += 5
    if _contains_any_token(name, _MOUSE_ZONE_TOKENS):
        score += 10

    if _is_color_capable_led(led_dir):
        score += 50

    brightness_path = led_dir / "brightness"
    if brightness_path.exists():
        if os.access(brightness_path, os.R_OK):
            score += 3
        if os.access(brightness_path, os.W_OK):
            score += 7

    return score


__all__ = ["_is_candidate_led", "_is_color_capable_led", "_leds_root", "_score_led_dir", "inspect_led_candidate"]