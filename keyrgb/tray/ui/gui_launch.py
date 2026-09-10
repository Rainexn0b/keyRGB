from __future__ import annotations

import json
import os

from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.runtime.imports import launch_module_subprocess

#: Internal tray -> per-key-editor snapshot for UX-04 preflight (JSON).
#: The per-key editor subprocess reads this instead of probing or opening
#: hardware. The payload carries JSON-native values only: normalized
#: capability booleans, the backend name, and dimensions.
PERKEY_PREFLIGHT_ENV_VAR = "KEYRGB_PERKEY_PREFLIGHT"

# Narrow boundary for reading the already-selected backend object. Mirrors
# the tray backend seam: never a broad silent ``Exception``.
_PERKEY_PREFLIGHT_BACKEND_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_MIN_PREFLIGHT_DIMENSION = 1
_MAX_PREFLIGHT_DIMENSION = 64


def _inherited_gui_environment() -> dict[str, str]:
    """Return the parent environment for GUI subprocesses."""

    env = dict(os.environ)
    env["KEYRGB_TRAY_MANAGED_GUI"] = "1"
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    return env


def _safe_perkey_backend_name(backend: object | None) -> str | None:
    """Read the name from the already-selected backend object only."""

    if backend is None:
        return None
    try:
        name = getattr(backend, "name", None)
    except _PERKEY_PREFLIGHT_BACKEND_ERRORS:
        return None
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _validate_preflight_dimensions(value: object) -> tuple[int, int] | None:
    """Return a valid ``(rows, cols)`` pair, else ``None`` (omitted)."""

    pair: object = tuple(value) if isinstance(value, list) else value
    if (
        isinstance(pair, tuple)
        and len(pair) == 2
        and all(type(item) is int for item in pair)
        and all(_MIN_PREFLIGHT_DIMENSION <= item <= _MAX_PREFLIGHT_DIMENSION for item in pair)
    ):
        rows, cols = pair
        return int(rows), int(cols)
    return None


def _safe_perkey_backend_dimensions(backend: object | None) -> tuple[int, int] | None:
    """Read ``(rows, cols)`` from the already-selected backend object only.

    This never selects, probes, or opens hardware: only the cached backend
    object's own ``dimensions()`` is consulted. ``None`` means the snapshot
    omits dimensions and the editor falls back to reference dimensions.
    """

    if backend is None:
        return None
    try:
        dimensions_fn = getattr(backend, "dimensions", None)
    except _PERKEY_PREFLIGHT_BACKEND_ERRORS:
        return None
    if not callable(dimensions_fn):
        return None
    try:
        raw_dimensions = dimensions_fn()
    except _PERKEY_PREFLIGHT_BACKEND_ERRORS:
        return None
    return _validate_preflight_dimensions(raw_dimensions)


def build_perkey_preflight_payload(
    backend_caps: object | None = None,
    backend_name: object | None = None,
    dimensions: object | None = None,
) -> dict[str, object]:
    """Build the JSON-safe UX-04 preflight snapshot payload.

    Capabilities are consumed exclusively through
    ``normalize_backend_capabilities`` (fails closed). The payload holds
    JSON-native values only: capability booleans, backend name, dimensions.
    """

    caps = normalize_backend_capabilities(backend_caps)
    name = backend_name.strip() if isinstance(backend_name, str) and backend_name.strip() else None
    valid_dimensions = _validate_preflight_dimensions(dimensions)
    return {
        "brightness": bool(caps.brightness),
        "per_key": bool(caps.per_key),
        "color": bool(caps.color),
        "hardware_effects": bool(caps.hardware_effects),
        "palette": bool(caps.palette),
        "backend_name": name,
        "dimensions": [valid_dimensions[0], valid_dimensions[1]] if valid_dimensions is not None else None,
    }


def perkey_preflight_snapshot_from_tray(
    tray: object,
) -> tuple[object | None, str | None, tuple[int, int] | None]:
    """Read the cached preflight snapshot from a tray instance.

    Uses only the already-cached ``tray.backend_caps`` and safe metadata
    from the already-selected ``tray.backend``. Never probes hardware,
    never opens a device, never selects a backend.
    """

    cached_caps = getattr(tray, "backend_caps", None)
    try:
        backend = getattr(tray, "backend", None)
    except _PERKEY_PREFLIGHT_BACKEND_ERRORS:
        backend = None
    return (
        cached_caps,
        _safe_perkey_backend_name(backend),
        _safe_perkey_backend_dimensions(backend),
    )


def launch_perkey_gui(
    backend_caps: object | None = None,
    backend_name: str | None = None,
    dimensions: object | None = None,
) -> None:
    """Launch the per-key editor GUI as a subprocess.

    Called with no arguments (existing callers/tests), no preflight
    snapshot is attached. When the tray passes its already-cached
    ``backend_caps``/name/dimensions, they are serialized through
    ``normalize_backend_capabilities`` into the internal
    ``KEYRGB_PERKEY_PREFLIGHT`` JSON env var so the editor can run its
    UX-04 preflight without probing or opening hardware.
    """

    env = _inherited_gui_environment()
    if backend_caps is None and backend_name is None and dimensions is None:
        env.pop(PERKEY_PREFLIGHT_ENV_VAR, None)
    else:
        payload = build_perkey_preflight_payload(
            backend_caps=backend_caps,
            backend_name=backend_name,
            dimensions=dimensions,
        )
        env[PERKEY_PREFLIGHT_ENV_VAR] = json.dumps(payload, sort_keys=True)
    launch_module_subprocess("keyrgb.gui.perkey", anchor=__file__, env=env)


def launch_uniform_gui(*, target_context: str = "keyboard", backend_name: str | None = None) -> None:
    """Launch the uniform color GUI as a subprocess."""

    env = _inherited_gui_environment()
    env["KEYRGB_UNIFORM_TARGET_CONTEXT"] = str(target_context or "keyboard").strip().lower() or "keyboard"
    if backend_name:
        env["KEYRGB_UNIFORM_BACKEND"] = str(backend_name).strip().lower()
    else:
        env.pop("KEYRGB_UNIFORM_BACKEND", None)
    launch_module_subprocess("keyrgb.gui.windows.uniform", anchor=__file__, env=env)


def launch_reactive_color_gui() -> None:
    """Launch the reactive typing color GUI as a subprocess."""

    launch_module_subprocess("keyrgb.gui.windows.reactive_color", anchor=__file__)


def launch_power_gui() -> None:
    """Launch the Settings GUI (power rules + autostart) as a subprocess."""

    env = dict(os.environ)
    # Settings runs in a separate process; tell it the tray PID so it can
    # avoid flagging the tray as an "other" USB holder.
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    launch_module_subprocess("keyrgb.gui.settings", anchor=__file__, env=env)


def launch_power_mode_settings_gui() -> None:
    """Launch the lightweight power mode settings GUI as a subprocess."""

    launch_module_subprocess("keyrgb.gui.windows.power_mode", anchor=__file__)


def launch_support_gui(*, focus: str = "debug") -> None:
    """Launch the support tools window as a subprocess."""

    env = dict(os.environ)
    env["KEYRGB_TRAY_PID"] = str(os.getpid())
    env["KEYRGB_SUPPORT_FOCUS"] = str(focus or "debug").strip().lower()
    launch_module_subprocess("keyrgb.gui.windows.support", anchor=__file__, env=env)
