from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.exceptions import is_device_disconnected

from .config_polling_internal.core import ConfigApplyState
from .config_polling_internal.core import apply_from_config_once as _apply_from_config_once_impl
from .config_polling_internal.core import (
    compute_config_apply_state as _compute_config_apply_state_impl,
)
from .config_polling_internal.core import maybe_apply_fast_path as _maybe_apply_fast_path_impl
from .config_polling_internal.core import state_for_log as _state_for_log_impl

from src.tray.protocols import ConfigPollingTrayProtocol


_CONFIG_POLLING_THREAD_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _compute_config_apply_state(tray: ConfigPollingTrayProtocol) -> ConfigApplyState:
    return _compute_config_apply_state_impl(tray)


def _state_for_log(state: ConfigApplyState | None):
    return _state_for_log_impl(state)


def _maybe_apply_fast_path(
    tray: ConfigPollingTrayProtocol,
    *,
    last_applied: ConfigApplyState | None,
    current: ConfigApplyState,
) -> tuple[bool, ConfigApplyState]:
    return _maybe_apply_fast_path_impl(
        tray,
        last_applied=last_applied,
        current=current,
        sw_effects_set=SW_EFFECTS,
    )


def _apply_from_config_once(
    tray: ConfigPollingTrayProtocol,
    *,
    ite_num_rows: int,
    ite_num_cols: int,
    cause: str,
    last_applied: ConfigApplyState | None,
    last_apply_warn_at: float,
) -> tuple[ConfigApplyState | None, float]:
    return _apply_from_config_once_impl(
        tray,
        ite_num_rows=ite_num_rows,
        ite_num_cols=ite_num_cols,
        cause=str(cause or "unknown"),
        last_applied=last_applied,
        last_apply_warn_at=last_apply_warn_at,
        monotonic_fn=time.monotonic,
        compute_state_fn=_compute_config_apply_state,
        state_for_log_fn=_state_for_log,
        maybe_apply_fast_path_fn=_maybe_apply_fast_path,
        is_device_disconnected_fn=is_device_disconnected,
    )


def start_config_polling(tray: ConfigPollingTrayProtocol, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_digest: str | None = None
    last_applied: ConfigApplyState | None = None
    last_apply_warn_at = 0.0

    def _file_digest(path: Path) -> str | None:
        try:
            data = path.read_bytes()
        except OSError:
            return None

        return hashlib.blake2s(data, digest_size=16).hexdigest()

    def _log_polling_exception(message: str, exc: Exception) -> None:
        try:
            tray._log_exception(message, exc)
        except (OSError, RuntimeError, TypeError, ValueError):
            pass

    def apply_from_config(*, cause: str) -> None:
        nonlocal last_applied
        nonlocal last_apply_warn_at
        last_applied, last_apply_warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=ite_num_rows,
            ite_num_cols=ite_num_cols,
            cause=str(cause or "unknown"),
            last_applied=last_applied,
            last_apply_warn_at=last_apply_warn_at,
        )

    def reload_and_apply_config(
        *,
        cause: str,
        error_message: str,
        last_error_at: float = 0.0,
        throttle_s: float | None = None,
    ) -> float:
        try:
            tray.config.reload()
            apply_from_config(cause=cause)
        except _CONFIG_POLLING_THREAD_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: config reload/apply in the polling thread is a best-effort runtime boundary; recoverable config or device failures must be logged and contained while unexpected defects still propagate
            if throttle_s is None:
                _log_polling_exception(error_message, exc)
                return last_error_at

            now = time.monotonic()
            if now - last_error_at > float(throttle_s):
                last_error_at = now
                _log_polling_exception(error_message, exc)

        return last_error_at

    def poll_config():
        nonlocal last_mtime
        nonlocal last_digest

        last_startup_error_at = 0.0

        try:
            last_mtime = config_path.stat().st_mtime
            last_digest = _file_digest(config_path)
        except FileNotFoundError:
            last_mtime = None
            last_digest = None

        last_startup_error_at = reload_and_apply_config(
            cause="startup",
            error_message="Error loading config on startup: %s",
            last_error_at=last_startup_error_at,
            throttle_s=30.0,
        )

        while True:
            try:
                mtime = config_path.stat().st_mtime
            except FileNotFoundError:
                mtime = None

            if mtime != last_mtime:
                last_mtime = mtime
                # Avoid noisy reload/apply cycles when the file is rewritten
                # without any content change (e.g., redundant saves).
                digest = _file_digest(config_path) if mtime is not None else None
                if digest is not None and digest == last_digest:
                    continue
                last_digest = digest
                reload_and_apply_config(
                    cause="mtime_change",
                    error_message="Error reloading config: %s",
                )

            time.sleep(0.1)

    threading.Thread(target=poll_config, daemon=True).start()
