from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

from ..base import BackendCapabilities, KeyboardBackend, KeyboardDevice, ProbeResult
from .device import AsusctlAuraKeyboardDevice

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    v = str(os.environ.get(name, "")).strip().lower()
    return v in {"1", "true", "yes", "on"}


def _parse_asusctl_zones(value: str) -> list[str]:
    zones: list[str] = []
    for part in (value or "").split(","):
        z = part.strip()
        if not z:
            continue
        zones.append(z)
    return zones


@dataclass
class AsusctlAuraBackend(KeyboardBackend):
    """Backend using the `asusctl` CLI.

    This is a pragmatic integration: it uses subprocess calls instead of re-
    implementing the Aura protocol.

    Configure zones (for virtual per-key support) via:
        KEYRGB_ASUSCTL_ZONES=one,two,three
    """

    name: str = "asusctl-aura"
    priority: int = 120

    def _asusctl_path(self) -> str:
        return os.environ.get("KEYRGB_ASUSCTL_PATH") or "asusctl"

    def _zones(self) -> list[str]:
        return _parse_asusctl_zones(os.environ.get("KEYRGB_ASUSCTL_ZONES", ""))

    def _run(self, args: list[str], *, timeout_s: float = 2.0) -> subprocess.CompletedProcess[str]:
        cmd = [self._asusctl_path(), *args]
        return subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        if _env_flag("KEYRGB_ASUSCTL_DISABLE"):
            return ProbeResult(available=False, reason="disabled by KEYRGB_ASUSCTL_DISABLE", confidence=0)

        exe = self._asusctl_path()
        if shutil.which(exe) is None:
            return ProbeResult(available=False, reason="asusctl not found", confidence=0)

        try:
            info = self._run(["info"], timeout_s=2.0)
        except Exception as exc:
            return ProbeResult(available=False, reason=f"asusctl info failed: {exc}", confidence=0)

        stdout = (info.stdout or "").strip()
        stderr = (info.stderr or "").strip()

        if info.returncode != 0:
            return ProbeResult(
                available=False,
                reason=f"asusctl info returned {info.returncode}: {stderr or stdout}",
                confidence=0,
            )

        if not stdout:
            return ProbeResult(available=False, reason="asusctl info produced no output", confidence=0)

        identifiers: dict[str, str] = {"asusctl": exe}
        for line in stdout.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip().lower().replace(" ", "_")
            v = v.strip()
            if k and v and k not in identifiers:
                identifiers[k] = v

        # Best-effort check that aura command exists.
        try:
            aura_help = self._run(["aura", "--help"], timeout_s=2.0)
            if aura_help.returncode == 0:
                identifiers["aura"] = "true"
        except Exception:
            pass

        # If asusctl is present and can talk to the system, we're likely the best
        # choice on ASUS hardware compared to generic sysfs kbd_backlight.
        return ProbeResult(
            available=True,
            reason="asusctl present",
            confidence=92,
            identifiers=identifiers,
        )

    def capabilities(self) -> BackendCapabilities:
        zones = self._zones()
        return BackendCapabilities(per_key=(len(zones) > 1), color=True, hardware_effects=False, palette=False)

    def get_device(self) -> KeyboardDevice:
        return AsusctlAuraKeyboardDevice(asusctl_path=self._asusctl_path(), zones=self._zones())

    def dimensions(self) -> tuple[int, int]:
        # Not a real per-key matrix backend (unless mapped to zones).
        return (6, 21)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
