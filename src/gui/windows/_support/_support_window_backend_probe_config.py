#!/usr/bin/env python3

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Protocol

from src.core.config._lighting._effect_speed_overrides import EffectSpeedOverrides


_PROBE_AUTO_STEP_DURATION_S = 2.5
_PROBE_AUTO_SETTLE_DURATION_S = 0.5
_PROBE_AUTOMATION_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


class _ProbeConfigLike(Protocol):
    _settings: object
    effect: object
    speed: object

    def _save(self) -> None: ...

    def set_effect_speed(self, effect_name: str, speed: int) -> None: ...


def _copy_effect_speeds(raw: object) -> dict[str, object] | None:
    return EffectSpeedOverrides.copied_from_settings(raw)


@dataclass(frozen=True, slots=True)
class ProbeConfigSnapshot:
    effect: str = "none"
    speed: int = 0
    effect_speeds: dict[str, object] | None = None

    @classmethod
    def capture(cls, config: _ProbeConfigLike) -> ProbeConfigSnapshot:
        effect_speeds = None
        settings = config._settings
        if isinstance(settings, dict):
            effect_speeds = _copy_effect_speeds(settings.get("effect_speeds"))

        try:
            speed = int(getattr(config, "speed", 0))
        except (TypeError, ValueError, OverflowError):
            speed = 0

        return cls(
            effect=str(getattr(config, "effect", "none") or "none"),
            speed=max(0, min(10, speed)),
            effect_speeds=effect_speeds,
        )

    @classmethod
    def from_snapshot(cls, snapshot: _SnapshotInput) -> ProbeConfigSnapshot:
        if isinstance(snapshot, cls):
            return snapshot

        effect_speeds = _copy_effect_speeds(snapshot.get("effect_speeds"))

        try:
            speed = int(snapshot.get("speed") or 0)
        except (TypeError, ValueError, OverflowError):
            speed = 0

        return cls(
            effect=str(snapshot.get("effect") or "none"),
            speed=max(0, min(10, speed)),
            effect_speeds=effect_speeds,
        )

    def effect_speeds_copy(self) -> dict[str, object] | None:
        return _copy_effect_speeds(self.effect_speeds)


_ProbePlan = dict[str, object]
_ProbeResult = dict[str, object]
_SnapshotInput = ProbeConfigSnapshot | dict[str, object]
_ProbeConfigFactory = Callable[[], _ProbeConfigLike]
_SleepFn = Callable[[float], None]
_ProbeConfigSnapshotFn = Callable[[_ProbeConfigLike], ProbeConfigSnapshot]


class _RestoreProbeConfigFn(Protocol):
    def __call__(self, config: _ProbeConfigLike, *, snapshot: _SnapshotInput) -> None: ...


def _format_probe_speed_list(values: object) -> str:
    if not isinstance(values, list):
        return ""

    out: list[str] = []
    for value in values:
        if isinstance(value, int | float):
            out.append(str(int(value)))
            continue
        text = str(value or "").strip()
        if text:
            out.append(text)
    return ", ".join(out)


def _tray_process_alive(tray_pid: object) -> bool:
    try:
        pid = int(str(tray_pid or "").strip())
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    return os.path.exists(f"/proc/{pid}")


def _probe_config_snapshot(config: _ProbeConfigLike) -> ProbeConfigSnapshot:
    return ProbeConfigSnapshot.capture(config)


def _restore_probe_config(config: _ProbeConfigLike, *, snapshot: _SnapshotInput) -> None:
    settings = config._settings
    save_fn = config._save
    probe_snapshot = ProbeConfigSnapshot.from_snapshot(snapshot)
    raw_effect_speeds = probe_snapshot.effect_speeds_copy()
    if isinstance(settings, dict) and callable(save_fn):
        if isinstance(raw_effect_speeds, dict) and raw_effect_speeds:
            settings["effect_speeds"] = dict(raw_effect_speeds)
        else:
            settings.pop("effect_speeds", None)
        save_fn()

    try:
        config.speed = int(probe_snapshot.speed or 0)
    except _PROBE_AUTOMATION_ERRORS:
        pass

    try:
        config.effect = str(probe_snapshot.effect or "none")
    except _PROBE_AUTOMATION_ERRORS:
        pass


def _auto_run_backend_speed_probe_via_tray_config(
    plan: _ProbePlan,
    *,
    config_cls: _ProbeConfigFactory,
    sleep_fn: _SleepFn,
    probe_config_snapshot_fn: _ProbeConfigSnapshotFn,
    restore_probe_config_fn: _RestoreProbeConfigFn,
) -> _ProbeResult:
    config = config_cls()
    snapshot = probe_config_snapshot_fn(config)
    effect_name = str(plan.get("effect_name") or "").strip()
    selection_effect_name = str(plan.get("selection_effect_name") or effect_name).strip() or effect_name
    requested_ui_speeds = [
        max(0, min(10, int(value)))
        for value in plan.get("requested_ui_speeds") or []
        if isinstance(value, int | float) or str(value).strip().isdigit()
    ]

    try:
        if selection_effect_name:
            config.effect = selection_effect_name
            sleep_fn(_PROBE_AUTO_SETTLE_DURATION_S)

        for ui_speed in requested_ui_speeds:
            config.set_effect_speed(effect_name, int(ui_speed))
            config.speed = int(ui_speed)
            sleep_fn(_PROBE_AUTO_STEP_DURATION_S)

        return {
            "execution_mode": "auto",
            "applied_ui_speeds": [int(value) for value in requested_ui_speeds],
            "step_duration_s": float(_PROBE_AUTO_STEP_DURATION_S),
            "settle_duration_s": float(_PROBE_AUTO_SETTLE_DURATION_S),
            "restored_effect": str(ProbeConfigSnapshot.from_snapshot(snapshot).effect or "none"),
        }
    finally:
        restore_probe_config_fn(config, snapshot=snapshot)
        sleep_fn(_PROBE_AUTO_SETTLE_DURATION_S)
