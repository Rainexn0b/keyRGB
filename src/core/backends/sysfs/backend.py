from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..base import BackendCapabilities, KeyboardDevice, KeyboardBackend, ProbeResult


def _leds_root() -> Path:
    # Test hook: allow overriding the sysfs root.
    root = os.environ.get("KEYRGB_SYSFS_LEDS_ROOT")

    # Safety: under pytest, never probe the real sysfs tree unless explicitly allowed.
    # Tests that want to exercise this backend should set KEYRGB_SYSFS_LEDS_ROOT to a temp dir.
    if root is None and os.environ.get("PYTEST_CURRENT_TEST") and not _hardware_allowed():
        return Path("/nonexistent-keyrgb-test-sysfs-leds")

    return Path(root or "/sys/class/leds")


def _hardware_allowed() -> bool:
    return os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"


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
    _safe_write_text(path, f"{int(value)}\n")


@dataclass
class SysfsLedKeyboardDevice(KeyboardDevice):
    brightness_path: Path
    max_brightness_path: Path
    led_dir: Path

    def _max(self) -> int:
        try:
            m = _read_int(self.max_brightness_path)
            return max(1, int(m))
        except Exception:
            return 1

    def _read_sysfs_brightness(self) -> int:
        try:
            return max(0, int(_read_int(self.brightness_path)))
        except Exception:
            return 0

    def turn_off(self) -> None:
        self.set_brightness(0)

    def is_off(self) -> bool:
        return self.get_brightness() <= 0

    def get_brightness(self) -> int:
        # Normalize sysfs brightness into KeyRGB's "hardware" 0..50 scale.
        sysfs_value = self._read_sysfs_brightness()
        max_value = self._max()
        return int(round((sysfs_value / max_value) * 50))

    def set_brightness(self, brightness: int) -> None:
        # Map KeyRGB's 0..50 brightness scale into sysfs range.
        b = max(0, min(50, int(brightness)))
        max_value = self._max()
        sysfs_value = int(round((b / 50) * max_value))
        _write_int(self.brightness_path, sysfs_value)

    def _supports_multicolor(self) -> bool:
        """Check if device supports multi_intensity (Tuxedo/Clevo RGB)"""
        multi_intensity_path = self.led_dir / "multi_intensity"
        return multi_intensity_path.exists()

    def _supports_color_attr(self) -> bool:
        """Check if device uses kernel driver with color attribute"""
        color_path = self.led_dir / "color"
        return color_path.exists()

    def set_color(self, color, *, brightness: int):
        """Enhanced color setting with multi_intensity and color attribute support"""
        # Try multi_intensity first (Tuxedo/Clevo)
        if self._supports_multicolor():
            r, g, b = color
            multi_intensity_path = self.led_dir / "multi_intensity"
            _safe_write_text(multi_intensity_path, f"{r} {g} {b}\n")
            self.set_brightness(brightness)
            return

        # Try color attribute (ITE kernel driver)
        if self._supports_color_attr():
            r, g, b = color
            hex_color = f"{r:02x}{g:02x}{b:02x}"
            color_path = self.led_dir / "color"
            _safe_write_text(color_path, f"{hex_color}\n")
            self.set_brightness(brightness)
            return

        # Fallback: brightness-only
        self.set_brightness(brightness)

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        # Not supported. No-op to avoid crashing if legacy code attempts per-key.
        self.set_brightness(brightness)

    def set_effect(self, effect_data) -> None:
        # Not supported. No-op.
        return


@dataclass
class SysfsLedsBackend(KeyboardBackend):
    name: str = "sysfs-leds"
    priority: int = 80

    def _find_led(self) -> Optional[tuple[Path, Path, Path]]:
        root = _leds_root()
        if not root.exists():
            return None

        candidates: list[Path] = []
        try:
            for child in root.iterdir():
                if child.is_dir() and _is_candidate_led(child.name):
                    candidates.append(child)
        except Exception:
            return None

        viable: list[tuple[int, str, Path]] = []
        for led_dir in candidates:
            b = led_dir / "brightness"
            m = led_dir / "max_brightness"
            if b.exists() and m.exists():
                viable.append((_score_led_dir(led_dir), led_dir.name, led_dir))

        if not viable:
            return None

        # Highest score wins; name is a deterministic tie-breaker.
        viable.sort(key=lambda t: (-t[0], t[1].lower()))
        best = viable[0][2]
        return best / "brightness", best / "max_brightness", best

        return None

    def probe(self) -> ProbeResult:
        found = self._find_led()
        if found is None:
            return ProbeResult(available=False, reason="no matching sysfs LED", confidence=0)

        brightness_path, max_brightness_path, led_dir = found
        if not os.access(brightness_path, os.R_OK):
            return ProbeResult(
                available=False,
                reason="brightness not readable",
                confidence=0,
                identifiers={
                    "brightness": str(brightness_path),
                    "led": led_dir.name,
                    "led_dir": str(led_dir),
                },
            )

        if not os.access(brightness_path, os.W_OK):
            return ProbeResult(
                available=False,
                reason="brightness not writable (udev permissions missing?)",
                confidence=0,
                identifiers={
                    "brightness": str(brightness_path),
                    "led": led_dir.name,
                    "led_dir": str(led_dir),
                },
            )

        return ProbeResult(
            available=True,
            reason="sysfs LED present",
            confidence=85,
            identifiers={
                "brightness": str(brightness_path),
                "max_brightness": str(max_brightness_path),
                "led": led_dir.name,
                "led_dir": str(led_dir),
                "supports_multi_intensity": str((led_dir / "multi_intensity").exists()).lower(),
                "supports_color_attr": str((led_dir / "color").exists()).lower(),
            },
        )

    def is_available(self) -> bool:
        return self.probe().available

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(per_key=False, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        found = self._find_led()
        if found is None:
            raise FileNotFoundError("No sysfs LED keyboard backlight found")
        brightness_path, max_brightness_path, led_dir = found
        return SysfsLedKeyboardDevice(
            brightness_path=brightness_path,
            max_brightness_path=max_brightness_path,
            led_dir=led_dir,
        )

    def dimensions(self) -> tuple[int, int]:
        # Not per-key. Return a common matrix size for legacy callers that assume
        # dimensions exist, but treat per_key=False as authoritative.
        return (6, 21)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
