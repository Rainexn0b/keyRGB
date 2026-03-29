from __future__ import annotations

import logging
from typing import Any, Optional
from src.core.utils.logging_utils import log_throttled

from src.core.system_power import PowerMode, get_status, set_mode

logger = logging.getLogger(__name__)


def _log_menu_debug(key: str, msg: str, exc: Exception, *, interval_s: float = 60) -> None:
    log_throttled(
        logger,
        key,
        interval_s=interval_s,
        level=logging.DEBUG,
        msg=msg,
        exc=exc,
    )


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
        _log_menu_debug(
            "tray.menu.tcc_profiles",
            "Failed to populate TCC profiles menu",
            exc,
            interval_s=120,
        )
        return None


def build_system_power_mode_menu(tray: Any, *, pystray: Any, item: Any) -> Optional[Any]:
    """Build a lightweight power mode submenu backed by cpufreq sysfs.

    Returns None when unsupported.
    """

    try:
        st = get_status()
        if not st.supported:
            return None
        can_apply = st.identifiers.get("can_apply") == "true"

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
                    update_menu = getattr(tray, "_update_menu", None)
                    if callable(update_menu):
                        update_menu()

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
        _log_menu_debug(
            "tray.menu.system_power",
            "Failed to populate system power mode menu",
            exc,
            interval_s=120,
        )
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
        _log_menu_debug(
            "tray.menu.perkey_profiles",
            "Failed to populate per-key profiles menu",
            exc,
            interval_s=120,
        )
        # Fallback: still allow opening the editor even if profiles list fails.
        return pystray.Menu(item("Open Color Editor…", tray._on_perkey_clicked))
