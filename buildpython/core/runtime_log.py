from __future__ import annotations

from src.core.diagnostics.runtime_capture import (
    RUNTIME_LAUNCHERS,
    RUNTIME_LOG_MODES,
    RUNTIME_LOG_NAME,
    RuntimeLogCaptureError,
    capture_runtime_log as _capture_runtime_log,
)

from ..utils.paths import repo_root


def capture_runtime_log(*, mode: str, launcher: str) -> int:
    """Compatibility facade for the diagnostics-owned runtime capture."""

    root = repo_root()
    return _capture_runtime_log(
        mode=mode,
        launcher=launcher,
        output_directory=root,
        source_root=root,
    )


__all__ = [
    "RUNTIME_LAUNCHERS",
    "RUNTIME_LOG_MODES",
    "RUNTIME_LOG_NAME",
    "RuntimeLogCaptureError",
    "capture_runtime_log",
]
