from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Literal, Optional


IdleAction = Optional[Literal["turn_off", "restore", "dim_to_temp", "restore_brightness"]]


def _compute_idle_action(
    *,
    dimmed: Optional[bool],
    screen_off: bool,
    is_off: bool,
    idle_forced_off: bool,
    dim_temp_active: bool,
    idle_timeout_s: float,
    power_management_enabled: bool,
    screen_dim_sync_enabled: bool,
    screen_dim_sync_mode: str,
    screen_dim_temp_brightness: int,
    brightness: int,
    user_forced_off: bool,
    power_forced_off: bool,
) -> IdleAction:
    if not power_management_enabled:
        return None

    if not screen_dim_sync_enabled:
        # If the feature is disabled, do not force off on dim events.
        # Still allow restoring lighting if it is unexpectedly off.
        if dimmed is None:
            if is_off and (not idle_forced_off):
                return "restore"
        return None

    if user_forced_off or power_forced_off:
        return None

    if int(brightness) <= 0:
        return None

    # Some desktops turn the display off via DPMS without changing backlight
    # brightness. Treat "screen off" as an effective dimmed signal.
    dimmed_effective: Optional[bool] = True if bool(screen_off) else dimmed

    # When we can't determine dim state, be conservative: don't force off and
    # don't restore temp brightness, but still allow restoring lighting if it is
    # unexpectedly off.
    if dimmed_effective is None:
        if dim_temp_active:
            return None
        if is_off and (not idle_forced_off):
            return "restore"
        return None

    if dimmed_effective is True:
        mode = str(screen_dim_sync_mode or "off").strip().lower()
        if mode == "temp":
            if not is_off:
                # In temp mode, dimming normally reduces to a temporary brightness.
                # But if the display is actually off (backlight at 0), match it by
                # turning the keyboard off.
                if bool(screen_off):
                    return "turn_off"
                return "dim_to_temp"
            return None

        if not is_off:
            return "turn_off"
        return None

    if dimmed_effective is False:
        if dim_temp_active:
            return "restore_brightness"

        # Not dimmed: restore if lighting is off (either we forced it off due to
        # dimming, or firmware/EC did something odd).
        if is_off:
            return "restore"
        return None

    return None


def _ensure_idle_state(tray: Any) -> None:
    if not hasattr(tray, "_idle_forced_off"):
        tray._idle_forced_off = False
    if not hasattr(tray, "_user_forced_off"):
        tray._user_forced_off = False
    if not hasattr(tray, "_power_forced_off"):
        tray._power_forced_off = False
    if not hasattr(tray, "_dim_backlight_baselines"):
        tray._dim_backlight_baselines = {}
    if not hasattr(tray, "_dim_temp_active"):
        tray._dim_temp_active = False
    if not hasattr(tray, "_dim_temp_target_brightness"):
        tray._dim_temp_target_brightness = None


def _read_int(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _read_dimmed_state(tray: Any) -> Optional[bool]:
    """Best-effort: infer 'dimmed' from kernel backlight brightness drops.

    Some systems expose multiple backlight devices (e.g., hybrid graphics). KDE
    may dim one while leaving others unchanged, so we track all devices and
    treat the display as dimmed if any device drops significantly vs baseline.
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


def _read_screen_off_state_drm() -> Optional[bool]:
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


def _run(argv: list[str], *, timeout_s: float = 1.0) -> Optional[str]:
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, check=False)
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    out = (cp.stdout or "").strip()
    return out or None


def _get_session_id() -> Optional[str]:
    sid = os.environ.get("XDG_SESSION_ID")
    if sid:
        return str(sid).strip() or None

    uid = os.getuid()
    # Try to find the user's "Display" session.
    out = _run(["loginctl", "show-user", str(uid), "-p", "Display", "--value"], timeout_s=1.0)
    if out:
        return out.strip() or None
    return None


def _read_logind_idle_seconds(*, session_id: str) -> Optional[float]:
    """Read idle time via logind IdleHint, best-effort.

    Note: logind IdleHint timing is DE-controlled.
    """

    out = _run(
        [
            "loginctl",
            "show-session",
            session_id,
            "-p",
            "IdleHint",
            "-p",
            "IdleSinceHintMonotonic",
        ],
        timeout_s=1.0,
    )
    if out is None:
        return None

    idle_hint_s: Optional[str] = None
    idle_since_us_s: Optional[str] = None
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "IdleHint":
            idle_hint_s = v
        elif k == "IdleSinceHintMonotonic":
            idle_since_us_s = v

    if idle_hint_s is None:
        return None

    s = idle_hint_s.strip().lower()
    if s in {"yes", "true", "1"}:
        is_idle = True
    elif s in {"no", "false", "0"}:
        is_idle = False
    else:
        return None

    if not is_idle:
        return 0.0

    try:
        idle_since_us = int((idle_since_us_s or "").strip())
        # logind returns microseconds from the monotonic clock.
        now_us = int(time.monotonic() * 1_000_000)
        idle_us = max(0, now_us - idle_since_us)
        return idle_us / 1_000_000.0
    except Exception:
        return None


def _restore_from_idle(tray: Any) -> None:
    tray.is_off = False
    tray._idle_forced_off = False

    # Best-effort: if brightness is 0, fall back to last brightness.
    try:
        if int(getattr(tray.config, "brightness", 0) or 0) == 0:
            tray.config.brightness = int(getattr(tray, "_last_brightness", 25) or 25)
    except Exception:
        pass

    try:
        tray._start_current_effect()
    except Exception:
        try:
            tray._log_exception("Failed to restore lighting after idle", Exception("restore failed"))
        except Exception:
            pass

    try:
        tray._refresh_ui()
    except Exception:
        pass


def start_idle_power_polling(
    tray: Any,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    idle_timeout_s: float = 60.0,
) -> None:
    """Power-management: sync keyboard lighting with display dimming.

    Desired behavior:
    - When the desktop dims the display, KeyRGB turns the keyboard LEDs off.
    - When the display returns to normal brightness, KeyRGB restores lighting.

    Implementation notes:
    - Uses kernel backlight brightness (/sys/class/backlight) to infer "dimmed".
    - Falls back to systemd-logind idle hint as a coarse signal when backlight
      state can't be read.
    - Best-effort only; never crashes the tray.
    """

    _ensure_idle_state(tray)

    def poll_idle_power() -> None:
        last_error_at = 0.0

        session_id = _get_session_id()

        while True:
            try:
                _ensure_idle_state(tray)

                # Always reload config here as well (best-effort). While the tray
                # has a dedicated config polling thread, reloading in this loop
                # ensures settings changes (especially screen-dim sync mode) take
                # effect even if the config polling thread is delayed or not
                # running for some reason.
                try:
                    tray.config.reload()
                except Exception:
                    pass

                dimmed = _read_dimmed_state(tray)
                # Screen-off can be inferred from backlight reaching 0, or from
                # DRM DPMS state when the desktop powers the display down.
                screen_off_backlight = bool(getattr(tray, "_dim_screen_off", False))
                screen_off_drm = _read_screen_off_state_drm()
                screen_off = bool(screen_off_backlight) or bool(screen_off_drm)

                # Coarse fallback when we can't infer dim state from backlight.
                if dimmed is None and session_id:
                    idle_s = _read_logind_idle_seconds(session_id=session_id)
                    dimmed = None if idle_s is None else (float(idle_s) >= float(idle_timeout_s))

                try:
                    power_mgmt_enabled = bool(getattr(tray.config, "power_management_enabled", True))
                    brightness = int(getattr(tray.config, "brightness", 0) or 0)

                    dim_sync_enabled = bool(getattr(tray.config, "screen_dim_sync_enabled", True))
                    dim_sync_mode = str(getattr(tray.config, "screen_dim_sync_mode", "off") or "off")
                    dim_temp_brightness = int(getattr(tray.config, "screen_dim_temp_brightness", 5) or 5)
                except Exception:
                    power_mgmt_enabled = True
                    brightness = 0
                    dim_sync_enabled = True
                    dim_sync_mode = "off"
                    dim_temp_brightness = 5

                if dim_temp_brightness < 1:
                    dim_temp_brightness = 1
                if dim_temp_brightness > 50:
                    dim_temp_brightness = 50

                action = _compute_idle_action(
                    dimmed=dimmed,
                    screen_off=bool(screen_off),
                    idle_timeout_s=float(idle_timeout_s),
                    is_off=bool(getattr(tray, "is_off", False)),
                    idle_forced_off=bool(getattr(tray, "_idle_forced_off", False)),
                    dim_temp_active=bool(getattr(tray, "_dim_temp_active", False)),
                    power_management_enabled=bool(power_mgmt_enabled),
                    screen_dim_sync_enabled=bool(dim_sync_enabled),
                    screen_dim_sync_mode=str(dim_sync_mode),
                    screen_dim_temp_brightness=int(dim_temp_brightness),
                    brightness=int(brightness),
                    user_forced_off=bool(getattr(tray, "_user_forced_off", False)),
                    power_forced_off=bool(getattr(tray, "_power_forced_off", False)),
                )

                if action == "turn_off":
                    tray._dim_temp_active = False
                    tray._dim_temp_target_brightness = None
                    try:
                        tray.engine.stop()
                    except Exception:
                        pass
                    try:
                        tray.engine.turn_off()
                    except Exception:
                        pass

                    tray.is_off = True
                    tray._idle_forced_off = True
                    try:
                        tray._refresh_ui()
                    except Exception:
                        pass

                elif action == "dim_to_temp":
                    # Do not fight explicit user/power forced off (already gated).
                    # Do not turn on lighting if it's currently off.
                    if not bool(getattr(tray, "is_off", False)):
                        tray._dim_temp_active = True
                        tray._dim_temp_target_brightness = int(dim_temp_brightness)
                        try:
                            tray.engine.set_brightness(int(dim_temp_brightness))
                        except Exception:
                            pass

                elif action == "restore_brightness":
                    tray._dim_temp_active = False
                    tray._dim_temp_target_brightness = None
                    # Restore to current config brightness (it may have been changed while dimmed).
                    try:
                        target = int(getattr(tray.config, "brightness", 0) or 0)
                    except Exception:
                        target = 0
                    if target > 0 and not bool(getattr(tray, "is_off", False)):
                        try:
                            tray.engine.set_brightness(int(target))
                        except Exception:
                            pass

                elif action == "restore":
                    # Only auto-restore if this wasn't an explicit user off.
                    if not bool(getattr(tray, "_user_forced_off", False)) and not bool(
                        getattr(tray, "_power_forced_off", False)
                    ):
                        tray._dim_temp_active = False
                        tray._dim_temp_target_brightness = None
                        _restore_from_idle(tray)

                time.sleep(0.5)

            except Exception as exc:
                now = time.monotonic()
                if now - last_error_at > 30.0:
                    last_error_at = now
                    try:
                        tray._log_exception("Idle power polling error: %s", exc)
                    except Exception:
                        pass

    threading.Thread(target=poll_idle_power, daemon=True).start()


__all__ = [
    "start_idle_power_polling",
    "_compute_idle_action",
]
