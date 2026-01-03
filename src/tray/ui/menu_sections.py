from __future__ import annotations

import logging
from typing import Any, Optional
from src.core.logging_utils import log_throttled

from src.core.system_power import PowerMode, get_status, set_mode


logger = logging.getLogger(__name__)


HW_EFFECTS = {"rainbow", "breathing", "wave", "ripple", "marquee", "raindrop", "aurora", "fireworks"}
SW_EFFECTS = {
    "rainbow_wave",
    "rainbow_swirl",
    "spectrum_cycle",
    "color_cycle",
    "chase",
    "twinkle",
    "strobe",
    "reactive_fade",
    "reactive_ripple",
    "reactive_rainbow",
    "reactive_snake",
}


def _log_menu_debug(key: str, msg: str, exc: Exception, *, interval_s: float = 60) -> None:
    log_throttled(
        logger,
        key,
        interval_s=interval_s,
        level=logging.DEBUG,
        msg=msg,
        exc=exc,
    )


def _format_hex_id(val: str) -> str:
    s = (str(val or "").strip().lower() if val is not None else "")
    if s.startswith("0x"):
        s = s[2:]
    return s


def _title(name: str) -> str:
    n = str(name)
    if n == "reactive_fade":
        return "Reactive Typing (Fade)"
    if n == "reactive_ripple":
        return "Reactive Typing (Ripple)"
    if n == "reactive_rainbow":
        return "Reactive Rainbow"
    if n == "reactive_snake":
        return "Reactive Snake"
    if n == "rainbow_wave":
        return "Rainbow Wave"
    if n == "rainbow_swirl":
        return "Rainbow Swirl"
    if n == "spectrum_cycle":
        return "Spectrum Cycle"
    if n == "color_cycle":
        return "Color Cycle"
    return n.replace("_", " ").strip().title()


def _perkey_sw_suffix(effect_name: str) -> str:
    return _title(effect_name)


def keyboard_status_text(tray: Any) -> str:
    """Return a single-line keyboard/device status label for the tray menu.

    Intended for a read-only, always-visible header line.
    """

    device_available = probe_device_available(tray)
    if not device_available:
        return "⚠ Keyboard device not detected"

    backend = getattr(tray, "backend", None)
    backend_name = str(getattr(backend, "name", "unknown"))

    probe = getattr(tray, "backend_probe", None)
    identifiers = getattr(probe, "identifiers", None) if probe is not None else None
    identifiers = dict(identifiers or {})

    usb_vid = identifiers.get("usb_vid")
    usb_pid = identifiers.get("usb_pid")
    if usb_vid and usb_pid:
        vid = _format_hex_id(usb_vid)
        pid = _format_hex_id(usb_pid)
        if vid and pid:
            return f"✅ Keyboard: {backend_name} ({vid}:{pid})"

    # Sysfs backend: show which LED file is being used.
    brightness_path = identifiers.get("brightness")
    if brightness_path:
        return f"✅ Keyboard: {backend_name} ({brightness_path})"

    return f"✅ Keyboard: {backend_name}"


def probe_device_available(tray: Any) -> bool:
    """Best-effort device availability probe.

    Tries the engine's private ensure method when present, then returns the
    engine's device_available flag (defaulting to True if unknown).
    """

    try:
        ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except Exception as exc:
        _log_menu_debug("tray.menu.ensure_device", "Failed to ensure device availability", exc, interval_s=60)

    return bool(getattr(getattr(tray, "engine", None), "device_available", True))


def tray_lighting_mode_text(tray: Any) -> str:
    """Return a single-line status indicator for the tray menu.

    Placed near the bottom of the menu so users can quickly see what is active
    (uniform/per-key profile, and whether a HW/SW effect is running).
    """

    # Off is the highest priority state.
    if bool(getattr(tray, "is_off", False)) or int(getattr(getattr(tray, "config", None), "brightness", 0) or 0) == 0:
        return "🔎 Active: Off"

    cfg = getattr(tray, "config", None)
    effect = str(getattr(cfg, "effect", "none") or "none")

    # Per-key mode is a first-class state.
    if effect == "perkey":
        try:
            from src.core.profile import profiles

            active_profile = str(profiles.get_active_profile())
        except Exception:
            active_profile = "(unknown)"

        return f"🔎 Active: Per-key ({active_profile})"

    # Uniform color is represented by no effect.
    if effect == "none":
        return "🔎 Active: Uniform"

    # Effects.
    if effect in HW_EFFECTS:
        return f"🔎 Active: HW {_title(effect)}"
    if effect in SW_EFFECTS:
        return f"🔎 Active: SW {_title(effect)}"

    return f"🔎 Active: {_title(effect)}"


def build_tcc_profiles_menu(tray: Any, *, pystray: Any, item: Any, tcc: Any) -> Optional[Any]:
    """Build the TCC profiles submenu (or return None if unavailable)."""

    def _make_tcc_profile_callback(profile_id: str):
        def _cb(_icon, _item):
            try:
                tray._on_tcc_profile_clicked(profile_id)
            except Exception as exc:
                _log_menu_debug(
                    "tray.menu.tcc_profile_click",
                    "TCC profile activation callback failed",
                    exc,
                    interval_s=60,
                )

        return _cb

    try:
        tcc_profiles = tcc.list_profiles()
        active = tcc.get_active_profile()
        if not tcc_profiles:
            return None

        profiles_items = [
            item(
                p.name,
                _make_tcc_profile_callback(p.id),
                checked=lambda _i, pid=p.id: (active is not None and active.id == pid),
                radio=True,
            )
            for p in tcc_profiles
        ]

        return pystray.Menu(
            item("Open Power Profiles…", tray._on_tcc_profiles_gui_clicked),
            pystray.Menu.SEPARATOR,
            *profiles_items,
        )
    except Exception as exc:
        _log_menu_debug("tray.menu.tcc_profiles", "Failed to populate TCC profiles menu", exc, interval_s=120)
        return None


def build_system_power_mode_menu(tray: Any, *, pystray: Any, item: Any) -> Optional[Any]:
    """Build a lightweight power mode submenu backed by cpufreq sysfs.

    Returns None when unsupported.
    """

    try:
        st = get_status()
        if not st.supported:
            return None
        can_apply = (st.identifiers.get("can_apply") == "true")

        def _make_cb(mode: PowerMode):
            def _cb(_icon, _item):
                try:
                    ok = set_mode(mode)
                    tray._system_power_last_ok = bool(ok)
                except Exception as exc:
                    tray._system_power_last_ok = False
                    _log_menu_debug(
                        "tray.menu.system_power.click",
                        "System power mode activation failed",
                        exc,
                        interval_s=60,
                    )
                finally:
                    if hasattr(tray, "_update_menu"):
                        tray._update_menu()

            return _cb

        def _checked(mode: PowerMode):
            return lambda _i, m=mode: (get_status().mode == m)

        # Keep labels simple and user-facing.
        return pystray.Menu(
            item(
                "Extreme Saver",
                _make_cb(PowerMode.EXTREME_SAVER),
                checked=_checked(PowerMode.EXTREME_SAVER),
                enabled=can_apply,
                radio=True,
            ),
            item(
                "Balanced",
                _make_cb(PowerMode.BALANCED),
                checked=_checked(PowerMode.BALANCED),
                enabled=can_apply,
                radio=True,
            ),
            item(
                "Performance",
                _make_cb(PowerMode.PERFORMANCE),
                checked=_checked(PowerMode.PERFORMANCE),
                enabled=can_apply,
                radio=True,
            ),
        )
    except Exception as exc:
        _log_menu_debug("tray.menu.system_power", "Failed to populate system power mode menu", exc, interval_s=120)
        return None


def build_perkey_profiles_menu(tray: Any, *, pystray: Any, item: Any, per_key_supported: bool) -> Optional[Any]:
    """Build the per-key profiles submenu.

    Returns None when per-key is not supported.
    """

    if not per_key_supported:
        return None

    def _make_perkey_profile_callback(profile_name: str):
        def _cb(_icon, _item):
            try:
                from src.core.profile import profiles as core_profiles

                name = core_profiles.set_active_profile(profile_name)
                colors = core_profiles.load_per_key_colors(name)
                core_profiles.apply_profile_to_config(tray.config, colors)

                # If the user explicitly chose a profile, treat it like an effect selection.
                # Respect power manager forced-off state.
                if not getattr(tray, "_power_forced_off", False):
                    tray.is_off = False
                    tray._start_current_effect()

                tray._update_icon()
                tray._update_menu()
            except Exception as exc:
                _log_menu_debug(
                    "tray.menu.perkey_profile_click",
                    "Per-key profile activation callback failed",
                    exc,
                    interval_s=60,
                )

        return _cb

    try:
        from src.core.profile import profiles as core_profiles

        perkey_profiles = core_profiles.list_profiles()
        active_profile = core_profiles.get_active_profile()

        profile_items = [
            item(
                name,
                _make_perkey_profile_callback(name),
                checked=lambda _i, n=name: active_profile == n,
                radio=True,
            )
            for name in perkey_profiles
        ]

        return pystray.Menu(
            item("Open Color Editor…", tray._on_perkey_clicked),
            pystray.Menu.SEPARATOR,
            *profile_items,
        )
    except Exception as exc:
        _log_menu_debug("tray.menu.perkey_profiles", "Failed to populate per-key profiles menu", exc, interval_s=120)
        # Fallback: still allow opening the editor even if profiles list fails.
        return pystray.Menu(item("Open Color Editor…", tray._on_perkey_clicked))
