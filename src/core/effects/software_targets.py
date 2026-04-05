from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol, TypeVar, cast

from src.core.effects.transitions import avoid_full_black
from src.core.utils.exceptions import is_permission_denied
from src.core.utils.logging_utils import log_throttled

SOFTWARE_EFFECT_TARGET_KEYBOARD = "keyboard"
SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE = "all_uniform_capable"
SOFTWARE_EFFECT_TARGETS = (
    SOFTWARE_EFFECT_TARGET_KEYBOARD,
    SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
)

Color = tuple[int, int, int]
KeyT = TypeVar("KeyT")
LOGGER = logging.getLogger(__name__)


class _UniformRenderDeviceProtocol(Protocol):
    def set_color(self, color: Color, *, brightness: int) -> object: ...


class _SecondaryTargetsProviderProtocol(Protocol):
    def __call__(self) -> Iterable[object]: ...


class _SoftwareRenderEngineProtocol(Protocol):
    @property
    def kb(self) -> _UniformRenderDeviceProtocol | None: ...

    @property
    def software_effect_target(self) -> object: ...

    @property
    def secondary_software_targets_provider(self) -> _SecondaryTargetsProviderProtocol | None: ...

    @property
    def _permission_error_cb(self) -> Callable[[Exception], None] | None: ...


@dataclass(frozen=True)
class SoftwareRenderTarget:
    key: str
    device_type: str
    device: _UniformRenderDeviceProtocol | None
    supports_per_key: bool = False


def normalize_software_effect_target(value: object) -> str:
    if not isinstance(value, str):
        return SOFTWARE_EFFECT_TARGET_KEYBOARD

    normalized = value.strip().lower()
    if normalized in SOFTWARE_EFFECT_TARGETS:
        return normalized
    return SOFTWARE_EFFECT_TARGET_KEYBOARD


def software_render_targets(engine: object) -> list[SoftwareRenderTarget]:
    primary_device = cast(_UniformRenderDeviceProtocol | None, getattr(engine, "kb", None))
    targets = [
        SoftwareRenderTarget(
            key="keyboard",
            device_type="keyboard",
            device=primary_device,
            supports_per_key=bool(getattr(primary_device, "set_key_colors", None)),
        )
    ]

    if (
        normalize_software_effect_target(getattr(engine, "software_effect_target", None))
        != SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
    ):
        return targets

    provider = cast(
        _SecondaryTargetsProviderProtocol | None, getattr(engine, "secondary_software_targets_provider", None)
    )
    if not callable(provider):
        return targets

    try:
        provided = provider()
    except Exception:  # @quality-exception exception-transparency: provider callbacks are runtime extension seams and broken providers must degrade to keyboard-only fanout
        LOGGER.exception("Secondary software target provider failed")
        return targets

    if not isinstance(provided, Iterable):
        return targets

    for raw_target in provided:
        target = _coerce_target(raw_target)
        if target is None:
            continue
        if str(target.key or "").strip().lower() == "keyboard":
            continue
        targets.append(target)

    return targets


def average_color_map(color_map: Mapping[KeyT, Color]) -> Color:
    if not color_map:
        return (0, 0, 0)

    red = sum(color[0] for color in color_map.values())
    green = sum(color[1] for color in color_map.values())
    blue = sum(color[2] for color in color_map.values())
    count = max(1, len(color_map))
    return (int(red / count), int(green / count), int(blue / count))


def _permission_error_callback_or_none(engine: object) -> Callable[[Exception], None] | None:
    try:
        return cast(_SoftwareRenderEngineProtocol, engine)._permission_error_cb
    except AttributeError:
        return None


def render_secondary_uniform_rgb(
    engine: object,
    *,
    rgb: Color,
    brightness_hw: int,
    logger: logging.Logger,
    log_key: str,
) -> None:
    targets = software_render_targets(engine)[1:]
    if not targets:
        return

    red, green, blue = avoid_full_black(rgb=rgb, target_rgb=rgb, brightness=int(brightness_hw))
    permission_cb = _permission_error_callback_or_none(engine)

    for target in targets:
        if target.device is None:
            continue
        try:
            target.device.set_color((red, green, blue), brightness=int(brightness_hw))
        except Exception as exc:  # @quality-exception exception-transparency: secondary targets are runtime device seams and fanout must keep keyboard rendering alive
            if is_permission_denied(exc):
                _notify_permission_error(permission_cb, exc=exc, logger=logger, log_key=log_key, target_key=target.key)
            log_throttled(
                logger,
                f"{log_key}.{target.key}",
                interval_s=30,
                level=logging.WARNING,
                msg=f"Secondary software-effect render failed for {target.key}",
                exc=exc,
            )


def _notify_permission_error(
    permission_cb: Callable[[Exception], None] | None,
    *,
    exc: Exception,
    logger: logging.Logger,
    log_key: str,
    target_key: str,
) -> None:
    if not callable(permission_cb):
        return

    try:
        permission_cb(exc)
    except Exception as callback_exc:  # @quality-exception exception-transparency: permission callbacks are best-effort notification hooks and must remain non-fatal
        log_throttled(
            logger,
            f"{log_key}.{target_key}.permission-callback",
            interval_s=30,
            level=logging.WARNING,
            msg=f"Secondary software-effect permission callback failed for {target_key}",
            exc=callback_exc,
        )


def _coerce_target(raw_target: object) -> SoftwareRenderTarget | None:
    if isinstance(raw_target, SoftwareRenderTarget):
        return raw_target if raw_target.device is not None else None

    if isinstance(raw_target, dict):
        device = cast(_UniformRenderDeviceProtocol | None, raw_target.get("device"))
        if device is None:
            return None
        return SoftwareRenderTarget(
            key=str(raw_target.get("key") or raw_target.get("device_type") or "secondary"),
            device_type=str(raw_target.get("device_type") or "secondary"),
            device=device,
            supports_per_key=bool(raw_target.get("supports_per_key", False)),
        )

    device = cast(_UniformRenderDeviceProtocol | None, getattr(raw_target, "device", raw_target))
    if device is None:
        return None

    return SoftwareRenderTarget(
        key=str(getattr(raw_target, "key", getattr(raw_target, "device_type", "secondary")) or "secondary"),
        device_type=str(getattr(raw_target, "device_type", "secondary") or "secondary"),
        device=device,
        supports_per_key=bool(getattr(raw_target, "supports_per_key", False)),
    )


__all__ = [
    "SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE",
    "SOFTWARE_EFFECT_TARGET_KEYBOARD",
    "SOFTWARE_EFFECT_TARGETS",
    "SoftwareRenderTarget",
    "average_color_map",
    "normalize_software_effect_target",
    "render_secondary_uniform_rgb",
    "software_render_targets",
]
