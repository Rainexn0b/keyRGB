from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from src.core.resources.defaults import REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS

from ..base import BackendCapabilities, BackendStability, KeyboardBackend, KeyboardDevice, ProbeResult
from .device import AsusctlAuraKeyboardDevice

logger = logging.getLogger(__name__)

_RECOVERABLE_SUBPROCESS_EXCEPTIONS = (OSError, subprocess.SubprocessError)


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
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: None = None

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

    def _run_recoverable(
        self,
        args: list[str],
        *,
        timeout_s: float = 2.0,
        log_message: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str] | None, Exception | None]:
        try:
            return self._run(args, timeout_s=timeout_s), None
        except _RECOVERABLE_SUBPROCESS_EXCEPTIONS as exc:  # @quality-exception exception-transparency: asusctl probing uses a shared subprocess boundary; recoverable launch and timeout failures are centralized so required info probes degrade to unavailable and optional aura checks stay best-effort while programming bugs still surface
            if log_message:
                logger.exception(log_message)
            return None, exc

    def is_available(self) -> bool:
        return self.probe().available

    def probe(self) -> ProbeResult:
        if _env_flag("KEYRGB_ASUSCTL_DISABLE"):
            return ProbeResult(available=False, reason="disabled by KEYRGB_ASUSCTL_DISABLE", confidence=0)

        exe = self._asusctl_path()
        if shutil.which(exe) is None:
            return ProbeResult(available=False, reason="asusctl not found", confidence=0)

        info, info_error = self._run_recoverable(["info"], timeout_s=2.0, log_message="asusctl probe failed")
        if info_error is not None:
            return ProbeResult(available=False, reason=f"asusctl info failed: {info_error}", confidence=0)
        assert info is not None

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
        aura_help, _ = self._run_recoverable(["aura", "--help"], timeout_s=2.0)
        if aura_help is not None and aura_help.returncode == 0:
            identifiers["aura"] = "true"

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
        return (REFERENCE_MATRIX_ROWS, REFERENCE_MATRIX_COLS)

    def effects(self) -> dict[str, Any]:
        return {}

    def colors(self) -> dict[str, Any]:
        return {}
