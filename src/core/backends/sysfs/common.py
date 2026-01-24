from __future__ import annotations

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _hardware_allowed() -> bool:
    return os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"


def _leds_root() -> Path:
    # Test hook: allow overriding the sysfs root.
    root = os.environ.get("KEYRGB_SYSFS_LEDS_ROOT")

    # Safety: under pytest, never probe the real sysfs tree unless explicitly allowed.
    # Tests that want to exercise this backend should set KEYRGB_SYSFS_LEDS_ROOT to a temp dir.
    if root is None and os.environ.get("PYTEST_CURRENT_TEST") and not _hardware_allowed():
        return Path("/nonexistent-keyrgb-test-sysfs-leds")

    return Path(root or "/sys/class/leds")


def _is_real_sysfs_path(path: Path) -> bool:
    try:
        real = os.path.realpath(str(path))
        return real.startswith("/sys/")
    except Exception:
        return False


def _safe_write_text(path: Path, content: str) -> None:
    # Safety: tests must not mutate real hardware state by writing sysfs.
    if os.environ.get("PYTEST_CURRENT_TEST") and not _hardware_allowed() and _is_real_sysfs_path(path):
        if os.environ.get("KEYRGB_TEST_HARDWARE_TRIPWIRE") == "1":
            raise RuntimeError(f"Refusing to write real sysfs path under pytest: {path}")
        return
    path.write_text(content, encoding="utf-8")


def _is_candidate_led(name: str) -> bool:
    n = name.lower()
    return (
        "kbd" in n
        or "keyboard" in n
        or "rgb:kbd" in n  # Tuxedo/Clevo multicolor
        or "tuxedo::kbd" in n  # Tuxedo WMI
        or "clevo::kbd" in n  # Clevo WMI
        or "ite_8291_lb" in n  # ITE lightbar
        or "hp_omen::kbd" in n  # HP Omen
        or "dell::kbd" in n  # Dell
        or "tpacpi::kbd" in n  # ThinkPad
        or "asus::kbd" in n  # ASUS WMI
        or "system76::kbd" in n  # System76
    )


def _score_led_dir(led_dir: Path) -> int:
    """Score a sysfs LED directory for likelihood of being a keyboard backlight.

    Many systems expose multiple LED class devices. We prefer candidates that:
    - look like the keyboard backlight (name-based heuristics)
    - support RGB (multi_intensity or color attribute)
    - are writable
    """

    name = led_dir.name.lower()
    score = 0

    # Strong signals.
    if "kbd_backlight" in name:
        score += 40
    if name.endswith("kbd_backlight"):
        score += 10
    if "keyboard" in name:
        score += 5

    # Prefer RGB-capable sysfs nodes.
    if (led_dir / "multi_intensity").exists():
        score += 50
    if (led_dir / "color").exists():
        score += 45
    if (led_dir / "rgb").exists():
        score += 45
    if (led_dir / "color_center").exists() or (led_dir / "color_left").exists():
        score += 45

    # De-prioritize "noise" LEDs that frequently contain kbd substrings.
    for noisy in ("capslock", "numlock", "scrolllock", "micmute", "mute"):
        if noisy in name:
            score -= 60

    b = led_dir / "brightness"
    if b.exists():
        if os.access(b, os.R_OK):
            score += 3
        if os.access(b, os.W_OK):
            score += 7

    return score


def _read_int(path: Path) -> int:
    return int(path.read_text(encoding="utf-8").strip())


def _write_int(path: Path, value: int) -> None:
    try:
        # When KEYRGB_DEBUG_BRIGHTNESS=1, emit a log for every sysfs write
        # performed by the backend (helps diagnose flash / transient writes).
        if os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1":
            logger.info("sysfs.write %s <- %s", path, int(value))
    except Exception:
        pass
    _safe_write_text(path, f"{int(value)}\n")
