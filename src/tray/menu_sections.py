from __future__ import annotations

import logging
from typing import Any, Optional
from src.core.logging_utils import log_throttled


logger = logging.getLogger(__name__)


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
        log_throttled(
            logger,
            "tray.menu.ensure_device",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to ensure device availability",
            exc=exc,
        )

    return bool(getattr(getattr(tray, "engine", None), "device_available", True))


def build_tcc_profiles_menu(tray: Any, *, pystray: Any, item: Any, tcc: Any) -> Optional[Any]:
    """Build the TCC profiles submenu (or return None if unavailable)."""

    def _make_tcc_profile_callback(profile_id: str):
        def _cb(_icon, _item):
            try:
                tray._on_tcc_profile_clicked(profile_id)
            except Exception as exc:
                log_throttled(
                    logger,
                    "tray.menu.tcc_profile_click",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="TCC profile activation callback failed",
                    exc=exc,
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
        log_throttled(
            logger,
            "tray.menu.tcc_profiles",
            interval_s=120,
            level=logging.DEBUG,
            msg="Failed to populate TCC profiles menu",
            exc=exc,
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
                from src.core import profiles as core_profiles

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
                log_throttled(
                    logger,
                    "tray.menu.perkey_profile_click",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="Per-key profile activation callback failed",
                    exc=exc,
                )

        return _cb

    try:
        from src.core import profiles as core_profiles

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
        log_throttled(
            logger,
            "tray.menu.perkey_profiles",
            interval_s=120,
            level=logging.DEBUG,
            msg="Failed to populate per-key profiles menu",
            exc=exc,
        )
        # Fallback: still allow opening the editor even if profiles list fails.
        return pystray.Menu(item("Open Color Editor…", tray._on_perkey_clicked))
