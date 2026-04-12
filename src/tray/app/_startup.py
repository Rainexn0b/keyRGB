from __future__ import annotations

from collections.abc import Callable
from typing import Any


_STARTUP_MIGRATION_ERRORS = (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def migrate_builtin_profile_brightness_best_effort(config: Any) -> None:
    try:
        from src.core.profile import profiles as core_profiles

        core_profiles.migrate_builtin_profile_brightness(config)
    except _STARTUP_MIGRATION_ERRORS:  # @quality-exception exception-transparency: optional startup migration boundary
        return


def create_effects_engine(EffectsEngine: Any, *, backend: Any) -> Any:
    try:
        return EffectsEngine(backend=backend)
    except TypeError:
        engine = EffectsEngine()
        set_backend = getattr(engine, "set_backend", None)
        if callable(set_backend):
            try:
                set_backend(backend)
            except (TypeError, RuntimeError, ValueError):
                pass
        return engine


def install_permission_error_callback_best_effort(engine: Any, callback: Callable[[Exception | None], None]) -> None:
    try:
        engine._permission_error_cb = callback
    except (AttributeError, RuntimeError):
        return


def build_permission_denied_message(backend_name: str) -> str:
    repo_url = "https://github.com/Rainexn0b/keyRGB"
    msg_lines = [
        "KeyRGB was blocked by missing permissions while updating keyboard lighting.",
        "",
        "Fix:",
        "  • Re-run KeyRGB's installer (installs udev rules / helpers)",
        "  • Reload udev rules: sudo udevadm control --reload-rules && sudo udevadm trigger",
        "  • Replug the device or reboot",
    ]
    if backend_name == "ite8291r3":
        msg_lines.append("  • ITE USB devices usually need /etc/udev/rules.d/99-ite8291-wootbook.rules")
    elif backend_name == "sysfs-leds":
        msg_lines.append(
            "  • Sysfs LED nodes may require /etc/udev/rules.d/99-keyrgb-sysfs-leds.rules or a polkit helper"
        )
    msg_lines.append("")
    msg_lines.append(repo_url)
    return "\n".join(msg_lines)


def flush_pending_notifications(tray: Any) -> None:
    pending_store = vars(tray).get("_pending_notifications")
    pending = list(pending_store) if isinstance(pending_store, list) else []
    if isinstance(pending_store, list):
        pending_store.clear()
    for title, message in pending:
        tray._notify(title, message)
