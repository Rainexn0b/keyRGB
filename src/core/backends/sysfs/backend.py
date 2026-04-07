from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS

from ..base import BackendCapabilities, BackendStability, KeyboardDevice, KeyboardBackend, ProbeResult
from . import common
from . import privileged
from .device import SysfsLedKeyboardDevice

logger = logging.getLogger(__name__)

_SYSFS_ENUMERATION_ERRORS = (OSError,)
_SYSFS_METADATA_ERRORS = (OSError,)


def _safe_access(path: Path, mode: int) -> bool:
    try:
        return bool(os.access(path, mode))
    except _SYSFS_METADATA_ERRORS:
        return False


@dataclass
class SysfsLedsBackend(KeyboardBackend):
    name: str = "sysfs-leds"
    priority: int = 150
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: None = None

    def _find_leds(self) -> list[Path]:
        root = common._leds_root()
        if not root.exists():
            return []

        candidates: list[Path] = []
        try:
            for child in root.iterdir():
                if child.is_dir() and common._is_candidate_led(child.name):
                    candidates.append(child)
        except _SYSFS_ENUMERATION_ERRORS:
            return []

        viable: list[tuple[int, str, Path]] = []
        for led_dir in candidates:
            b = led_dir / "brightness"
            m = led_dir / "max_brightness"
            if not (b.exists() and m.exists()):
                continue

            try:
                score = common._score_led_dir(led_dir)
            except _SYSFS_METADATA_ERRORS:
                score = 0

            viable.append((score, led_dir.name, led_dir))

        if not viable:
            return []

        # Highest score first; name is a deterministic tie-breaker.
        viable.sort(key=lambda t: (-t[0], t[1].lower()))

        # Filter out low-scoring candidates (e.g. noise like "micmute" that slipped through)
        # 0 is the baseline for "neutral", negatives are explicit "bad matches".
        return [t[2] for t in viable if t[0] >= 0]

    def probe(self) -> ProbeResult:
        found = self._find_leds()
        if not found:
            return ProbeResult(available=False, reason="no matching sysfs LED", confidence=0)

        # Primary is the highest scoring one
        led_dir = found[0]
        brightness_path = led_dir / "brightness"
        max_brightness_path = led_dir / "max_brightness"

        identifiers: dict[str, str] = {
            "brightness": str(brightness_path),
            "led": led_dir.name,
            "led_dir": str(led_dir),
        }

        try:
            st = os.stat(brightness_path)
            identifiers["brightness_uid"] = str(int(st.st_uid))
            identifiers["brightness_gid"] = str(int(st.st_gid))
            identifiers["brightness_mode"] = f"{int(st.st_mode) & 0o777:04o}"
        except _SYSFS_METADATA_ERRORS:
            pass

        readable = _safe_access(brightness_path, os.R_OK)
        writable = _safe_access(brightness_path, os.W_OK)
        identifiers["brightness_readable"] = str(readable).lower()
        identifiers["brightness_writable"] = str(writable).lower()
        identifiers["helper_led_supported"] = str(privileged.helper_can_apply_led(led_dir.name)).lower()

        if not readable:
            return ProbeResult(
                available=False,
                reason="brightness not readable",
                confidence=0,
                identifiers=identifiers,
            )

        if not writable:
            # Many kernel LED class nodes are root-writable only. If the optional
            # pkexec helper is present and supports LED writes, we can still
            # drive the backlight safely without running the whole app as root.
            if privileged.helper_can_apply_led(led_dir.name) and privileged.helper_supports_led_apply():
                identifiers["helper"] = privileged.power_helper_path()
                return ProbeResult(
                    available=True,
                    reason="sysfs LED present (brightness root-only; using helper)",
                    confidence=70,
                    identifiers=identifiers,
                )

            return ProbeResult(
                available=False,
                reason="brightness not writable (needs root or a compatible keyrgb-power-helper LED path)",
                confidence=0,
                identifiers=identifiers,
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
                "supports_channel_rgb": str(led_dir.name.lower().startswith("ite_8297:")).lower(),
                "all_zones": str([p.name for p in found]),
            },
        )

    def is_available(self) -> bool:
        return self.probe().available

    def capabilities(self) -> BackendCapabilities:
        try:
            found = self._find_leds()
        except _SYSFS_ENUMERATION_ERRORS:
            found = []

        color_supported = False
        try:
            for led_dir in found[:8]:
                if any(
                    (
                        (led_dir / "multi_intensity").exists(),
                        (led_dir / "color").exists(),
                        (led_dir / "rgb").exists(),
                        (led_dir / "color_left").exists(),
                        (led_dir / "color_center").exists(),
                        (led_dir / "color_right").exists(),
                        (led_dir / "color_extra").exists(),
                    )
                ):
                    color_supported = True
                    break
        except _SYSFS_METADATA_ERRORS:
            color_supported = False

        return BackendCapabilities(per_key=False, color=bool(color_supported), hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        found = self._find_leds()
        if not found:
            raise FileNotFoundError("No sysfs LED keyboard backlight found")

        return SysfsLedKeyboardDevice(
            primary_led_dir=found[0],
            all_led_dirs=found,
        )

    def dimensions(self) -> tuple[int, int]:
        # Not per-key. Return a common matrix size for legacy callers that assume
        # dimensions exist, but treat per_key=False as authoritative.
        return (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
