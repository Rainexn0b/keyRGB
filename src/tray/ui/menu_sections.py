from __future__ import annotations

import logging
from typing import Any, Optional

from src.core.utils.logging_utils import log_throttled
from src.core.utils.safe_attrs import safe_int_attr

from src.core.power.system import PowerMode, get_status, set_mode
from .menu_status import device_context_controls_available


logger = logging.getLogger(__name__)

_MENU_BUILD_EXCEPTIONS = (AttributeError, RuntimeError, TypeError, ValueError)
_TCC_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (OSError,)
_SYSTEM_POWER_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (OSError,)
_SYSTEM_POWER_CALLBACK_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_PERKEY_MENU_EXCEPTIONS = _MENU_BUILD_EXCEPTIONS + (ImportError, OSError)


def _call_update_menu_if_present(tray: Any) -> None:
    try:
        update_menu = tray._update_menu
    except AttributeError:
        return
    if not callable(update_menu):
        return
    update_menu()


def _power_forced_off_or_false(tray: Any) -> bool:
    try:
        return bool(tray._power_forced_off)
    except AttributeError:
        return False


def _device_context_footer_items(tray: Any, *, pystray: Any, item: Any) -> list[Any]:
    return [
        pystray.Menu.SEPARATOR,
        item("Support Tools…", tray._on_support_debug_clicked),
        item("Settings", tray._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,
        item("Quit", tray._on_quit_clicked),
    ]


def _unsupported_device_context_text(device_label: str, status: str) -> str:
    return {
        "known_dormant": f"{device_label} detected, but this backend is still dormant in this build",
        "experimental_disabled": f"{device_label} backend is present but disabled by experimental-backend policy",
        "known_unavailable": f"{device_label} was identified, but it is not currently available for control",
        "unrecognized_ite": f"{device_label} was detected, but it is not recognized by a supported backend yet",
    }.get(status, f"{device_label} controls are not available in this build")


def _build_lightbar_context_menu_items(
    tray: Any, *, pystray: Any, item: Any, context_entry: dict[str, str]
) -> list[Any]:
    controls_available = device_context_controls_available(tray, context_entry)
    if controls_available:

        def _checked_lightbar_brightness(level: int):
            return lambda _item, expected=level: (
                safe_int_attr(tray.config, "lightbar_brightness", default=0) == expected * 5
            )

        brightness_menu = pystray.Menu(
            *[
                item(
                    str(level),
                    tray._on_selected_device_brightness_clicked,
                    checked=_checked_lightbar_brightness(level),
                    radio=True,
                )
                for level in range(0, 11)
            ]
        )
        body = [
            item("Color…", tray._on_selected_device_color_clicked),
            item("Brightness", brightness_menu),
            pystray.Menu.SEPARATOR,
            item("Turn Off", tray._on_selected_device_turn_off_clicked),
        ]
    else:
        body = [
            item(
                _unsupported_device_context_text("Lightbar", str(context_entry.get("status") or "").strip()),
                lambda _icon, _item: None,
                enabled=False,
            )
        ]

    return [*body, *_device_context_footer_items(tray, pystray=pystray, item=item)]


def _build_generic_device_context_menu_items(
    tray: Any,
    *,
    pystray: Any,
    item: Any,
    context_entry: dict[str, str],
) -> list[Any]:
    device_label = str(context_entry.get("device_type") or "device").replace("_", " ").title()
    controls_available = device_context_controls_available(tray, context_entry)
    if controls_available:
        body = [
            item(
                f"{device_label} controls will be provided by its dedicated controller surface",
                lambda _icon, _item: None,
                enabled=False,
            )
        ]
    else:
        body = [
            item(
                _unsupported_device_context_text(device_label, str(context_entry.get("status") or "").strip()),
                lambda _icon, _item: None,
                enabled=False,
            )
        ]

    return [*body, *_device_context_footer_items(tray, pystray=pystray, item=item)]


_DEVICE_CONTEXT_MENU_BUILDERS = {
    "lightbar": _build_lightbar_context_menu_items,
}


def build_device_context_menu_items(tray: Any, *, pystray: Any, item: Any, context_entry: dict[str, str]) -> list[Any]:
    """Build a selected device-context surface for non-keyboard devices."""

    device_type = str(context_entry.get("device_type") or "").strip().lower()
    builder = _DEVICE_CONTEXT_MENU_BUILDERS.get(device_type, _build_generic_device_context_menu_items)
    return builder(tray, pystray=pystray, item=item, context_entry=context_entry)


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
            except Exception as exc:  # @quality-exception exception-transparency: tray profile activation crosses UI and runtime backend boundaries and must remain best-effort
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
                checked=lambda _i, pid=p.id: active is not None and active.id == pid,
                radio=True,
            )
            for p in tcc_profiles
        ]

        return pystray.Menu(
            item("Open Power Profiles…", tray._on_tcc_profiles_gui_clicked),
            pystray.Menu.SEPARATOR,
            *profiles_items,
        )
    except _TCC_MENU_EXCEPTIONS as exc:
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
                except _SYSTEM_POWER_CALLBACK_EXCEPTIONS as exc:
                    tray._system_power_last_ok = False
                    _log_menu_debug(
                        "tray.menu.system_power.click",
                        "System power mode activation failed",
                        exc,
                        interval_s=60,
                    )
                finally:
                    _call_update_menu_if_present(tray)

            return _cb

        def _checked(mode: PowerMode):
            return lambda _i, m=mode: get_status().mode == m

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
    except _SYSTEM_POWER_MENU_EXCEPTIONS as exc:
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
                if not _power_forced_off_or_false(tray):
                    tray.is_off = False
                    tray._start_current_effect()

                tray._update_icon()
                tray._update_menu()
            except Exception as exc:  # @quality-exception exception-transparency: per-key profile activation crosses persistence, UI, and runtime effect boundaries and must remain best-effort
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
    except _PERKEY_MENU_EXCEPTIONS as exc:
        _log_menu_debug(
            "tray.menu.perkey_profiles",
            "Failed to populate per-key profiles menu",
            exc,
            interval_s=120,
        )
        # Fallback: still allow opening the editor even if profiles list fails.
        return pystray.Menu(item("Open Color Editor…", tray._on_perkey_clicked))
