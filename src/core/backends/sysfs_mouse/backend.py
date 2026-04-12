from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.backends.base import (
    BackendCapabilities,
    BackendStability,
    ExperimentalEvidence,
    KeyboardBackend,
    KeyboardDevice,
    ProbeResult,
)
from src.core.backends.sysfs import privileged
from src.core.utils.safe_attrs import safe_int_attr

from . import common
from .device import SysfsMouseDevice

_SYSFS_ENUMERATION_ERRORS = (OSError,)
_SYSFS_METADATA_ERRORS = (OSError,)


def _safe_access(path: Path, mode: int) -> bool:
    try:
        return bool(os.access(path, mode))
    except _SYSFS_METADATA_ERRORS:
        return False


def _context_key_for_led_name(led_name: str) -> str:
    normalized = str(led_name or "").strip().lower().replace(":", "_")
    return f"mouse:sysfs:{normalized}" if normalized else "mouse"


@dataclass
class SysfsMouseBackend(KeyboardBackend):
    """Experimental auxiliary sysfs backend for external mouse LED nodes."""

    name: str = "sysfs-mouse"
    priority: int = 10
    stability: BackendStability = BackendStability.EXPERIMENTAL
    experimental_evidence: ExperimentalEvidence = ExperimentalEvidence.SPECULATIVE

    def _find_leds(self) -> list[Path]:
        root = common._leds_root()
        if not root.exists():
            return []

        candidates: list[Path] = []
        try:
            for child in root.iterdir():
                if child.is_dir() and common._is_candidate_led(child.name, led_dir=child):
                    candidates.append(child)
        except _SYSFS_ENUMERATION_ERRORS:
            return []

        viable: list[tuple[int, str, Path]] = []
        for led_dir in candidates:
            brightness_path = led_dir / "brightness"
            max_brightness_path = led_dir / "max_brightness"
            if not (brightness_path.exists() and max_brightness_path.exists()):
                continue
            if not common._is_color_capable_led(led_dir):
                continue
            try:
                score = common._score_led_dir(led_dir)
            except _SYSFS_METADATA_ERRORS:
                score = 0
            viable.append((score, led_dir.name, led_dir))

        viable.sort(key=lambda item: (-item[0], item[1].lower()))
        return [item[2] for item in viable if item[0] >= 0]

    def probe(self) -> ProbeResult:
        found = self._find_leds()
        if not found:
            return ProbeResult(available=False, reason="no matching sysfs mouse LED", confidence=0)

        led_dir = found[0]
        brightness_path = led_dir / "brightness"
        max_brightness_path = led_dir / "max_brightness"

        identifiers: dict[str, str] = {
            "device_type": "mouse",
            "context_key": _context_key_for_led_name(led_dir.name),
            "brightness": str(brightness_path),
            "max_brightness": str(max_brightness_path),
            "led": led_dir.name,
            "led_dir": str(led_dir),
        }

        readable = _safe_access(brightness_path, os.R_OK)
        writable = _safe_access(brightness_path, os.W_OK)
        identifiers["brightness_readable"] = str(readable).lower()
        identifiers["brightness_writable"] = str(writable).lower()
        identifiers["helper_led_supported"] = str(privileged.helper_can_apply_led(led_dir.name)).lower()

        if not readable:
            return ProbeResult(
                available=False, reason="mouse brightness not readable", confidence=0, identifiers=identifiers
            )

        experimental_enabled = bool(os.environ.get("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS") == "1")
        identifiers["experimental_enabled"] = str(experimental_enabled).lower()
        if not experimental_enabled:
            return ProbeResult(
                available=False,
                reason=(
                    "experimental backend disabled (detected sysfs mouse LED; enable Experimental backends in Settings "
                    "or set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1)"
                ),
                confidence=0,
                identifiers=identifiers,
            )

        if not writable:
            if privileged.helper_can_apply_led(led_dir.name) and privileged.helper_supports_led_apply():
                identifiers["helper"] = privileged.power_helper_path()
                return ProbeResult(
                    available=True,
                    reason="sysfs mouse LED present (brightness root-only; using helper)",
                    confidence=65,
                    identifiers=identifiers,
                )
            return ProbeResult(
                available=False,
                reason="mouse brightness not writable (needs root or a compatible keyrgb-power-helper LED path)",
                confidence=0,
                identifiers=identifiers,
            )

        return ProbeResult(
            available=True,
            reason="sysfs mouse LED present",
            confidence=75,
            identifiers=identifiers,
        )

    def is_available(self) -> bool:
        return self.probe().available

    def capabilities(self) -> BackendCapabilities:
        found = self._find_leds()
        color_supported = bool(found)
        return BackendCapabilities(per_key=False, color=color_supported, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        probe = self.probe()
        if not probe.available:
            reason = str(probe.reason or "sysfs mouse backend unavailable")
            if "experimental backend disabled" in reason.lower():
                raise RuntimeError(
                    "Sysfs mouse support is classified as experimental. Enable Experimental backends in Settings or "
                    "set KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 before using it."
                )
            raise FileNotFoundError(reason)

        found = self._find_leds()
        if not found:
            raise FileNotFoundError("No sysfs mouse LED found")

        return SysfsMouseDevice(primary_led_dir=found[0], all_led_dirs=found)

    def dimensions(self) -> tuple[int, int]:
        return (1, max(1, safe_int_attr(self, "_zone_count_hint", default=1)))

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}


__all__ = ["SysfsMouseBackend"]
