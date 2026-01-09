from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

from src.core.effects.catalog import SW_EFFECTS_SET as SW_EFFECTS
from src.core.utils.exceptions import is_device_disconnected

from ._config_polling_core import ConfigApplyState
from ._config_polling_core import apply_from_config_once as _apply_from_config_once_impl
from ._config_polling_core import (
    compute_config_apply_state as _compute_config_apply_state_impl,
)
from ._config_polling_core import maybe_apply_fast_path as _maybe_apply_fast_path_impl
from ._config_polling_core import state_for_log as _state_for_log_impl


def _compute_config_apply_state(tray) -> ConfigApplyState:
    return _compute_config_apply_state_impl(tray)


def _state_for_log(state: ConfigApplyState | None):
    return _state_for_log_impl(state)


def _maybe_apply_fast_path(
    tray,
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
    tray,
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


def start_config_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Poll config file for external changes and apply them."""

    config_path = Path(tray.config.CONFIG_FILE)
    last_mtime = None
    last_digest: str | None = None
    last_applied: ConfigApplyState | None = None
    last_apply_warn_at = 0.0

    def _file_digest(path: Path) -> str | None:
        try:
            data = path.read_bytes()
        except Exception:
            return None
        try:
            return hashlib.blake2s(data, digest_size=16).hexdigest()
        except Exception:
            return None

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

        try:
            tray.config.reload()
            apply_from_config(cause="startup")
        except Exception as exc:
            # Don't crash the polling thread; but also don't silently eat errors.
            now = time.monotonic()
            if now - last_startup_error_at > 30:
                last_startup_error_at = now
                try:
                    tray._log_exception("Error loading config on startup: %s", exc)
                except (OSError, RuntimeError, ValueError):
                    pass

        while True:
            try:
                mtime = config_path.stat().st_mtime
            except FileNotFoundError:
                mtime = None

            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    # Avoid noisy reload/apply cycles when the file is rewritten
                    # without any content change (e.g., redundant saves).
                    digest = _file_digest(config_path) if mtime is not None else None
                    if digest is not None and digest == last_digest:
                        continue
                    last_digest = digest
                    tray.config.reload()
                    apply_from_config(cause="mtime_change")
                except Exception as e:
                    tray._log_exception("Error reloading config: %s", e)

            time.sleep(0.1)

    threading.Thread(target=poll_config, daemon=True).start()
