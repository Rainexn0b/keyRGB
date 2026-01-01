from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional


def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def read_dimmed_state(tray: Any) -> Optional[bool]:
    """Best-effort: infer 'dimmed' from kernel backlight brightness drops.

    Some systems expose multiple backlight devices (e.g., hybrid graphics). KDE
    may dim one while leaving others unchanged, so we track all devices and
    treat the display as dimmed if any device drops significantly vs baseline.

    Side effects:
        - Updates tray._dim_backlight_baselines and tray._dim_screen_off.
    """

    base = Path("/sys/class/backlight")
    if not base.exists():
        return None

    baselines: dict[str, int] = getattr(tray, "_dim_backlight_baselines", {})
    dimmed_any: Optional[bool] = None
    screen_off_any = False

    for child in base.iterdir():
        if not child.is_dir():
            continue

        current = _read_int(child / "brightness")
        max_brightness = _read_int(child / "max_brightness")
        if current is None or max_brightness is None or max_brightness <= 0:
            continue

        key = str(child)
        baseline = baselines.get(key)
        if baseline is None or baseline <= 0:
            baselines[key] = int(current)
            dimmed_any = False if dimmed_any is None else dimmed_any
            continue

        baseline_i = int(baseline)
        current_i = int(current)

        if current_i <= 0:
            screen_off_any = True

        # Significant drop detection: at least 10% and at least 1 step.
        dimmed = (current_i <= int(baseline_i * 0.90)) and ((baseline_i - current_i) >= 1)

        if dimmed:
            dimmed_any = True
        else:
            dimmed_any = False if dimmed_any is None else dimmed_any
            # Follow manual brightness changes while not dimmed.
            if current_i != baseline_i:
                baselines[key] = current_i

    tray._dim_backlight_baselines = baselines
    tray._dim_screen_off = bool(screen_off_any)
    return dimmed_any


def read_screen_off_state_drm() -> Optional[bool]:
    """Best-effort: detect whether the active display is powered off via DPMS.

    On some desktops (notably KDE), turning the screen off may not change
    /sys/class/backlight brightness but will flip DRM connector DPMS state.
    """

    base = Path("/sys/class/drm")
    if not base.exists():
        return None

    enabled_true = {"enabled", "1", "yes", "true"}
    enabled_false = {"disabled", "0", "no", "false"}

    connected: list[Path] = []
    connected_edp: list[Path] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue

        name = child.name
        if not (name.startswith("card") and "-" in name):
            continue

        try:
            status_s = (child / "status").read_text(encoding="utf-8").strip().lower()
        except Exception:
            continue
        if status_s != "connected":
            continue

        connected.append(child)
        if "edp" in name.lower():
            connected_edp.append(child)

    # Prefer internal panels: on some systems, when the display is powered off
    # via DPMS, the eDP connector flips to enabled=disabled + dpms=Off.
    candidates = connected_edp if connected_edp else connected
    if not candidates:
        return None

    observed_any = 0
    any_off = False

    for child in candidates:
        try:
            dpms_s = (child / "dpms").read_text(encoding="utf-8").strip().lower()
        except Exception:
            dpms_s = ""

        try:
            enabled_s = (child / "enabled").read_text(encoding="utf-8").strip().lower()
        except Exception:
            enabled_s = ""

        # If we don't have any useful signals, skip.
        if (not dpms_s) and (not enabled_s):
            continue

        observed_any += 1

        # For eDP: treat either dpms!=on OR enabled=false as screen-off.
        is_edp = "edp" in child.name.lower()
        if is_edp:
            if (dpms_s and dpms_s != "on") or (enabled_s in enabled_false):
                any_off = True
            continue

        # For external connectors: only consider those marked enabled/active.
        if enabled_s and (enabled_s not in enabled_true):
            continue
        if dpms_s and dpms_s != "on":
            any_off = True

    if observed_any <= 0:
        return None
    return bool(any_off)


def run(argv: list[str], *, timeout_s: float = 1.0) -> Optional[str]:
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, check=False)
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    out = (cp.stdout or "").strip()
    return out or None


def get_session_id() -> Optional[str]:
    sid = os.environ.get("XDG_SESSION_ID")
    if sid:
        return str(sid).strip() or None

    uid = os.getuid()
    out = run(["loginctl", "show-user", str(uid), "-p", "Display", "--value"], timeout_s=1.0)
    if out:
        return out

    out = run(
        [
            "loginctl",
            "list-sessions",
            "--no-legend",
            "--no-pager",
        ],
        timeout_s=1.0,
    )
    if not out:
        return None

    for line in out.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        session_id = parts[0]
        if session_id:
            return session_id

    return None
