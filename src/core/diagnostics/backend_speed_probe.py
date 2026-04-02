from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from src.core.backends.ite8910 import protocol as ite8910_protocol
from src.core.backends.ite8910.backend import Ite8910Backend
from src.core.effects.hw_payloads import build_hw_effect_payload

ITE8910_SPEED_PROBE_KEY = "ite8910_speed"
ITE8910_SPEED_PROBE_EFFECT = "spectrum_cycle"
ITE8910_SPEED_PROBE_UI_SPEEDS: tuple[int, ...] = (1, 3, 5, 7, 10)


class _ProbeKeyboard:
    keyrgb_hw_speed_policy = "direct"

    def set_palette_color(self, _slot: int, _color: object) -> None:
        return


def _normalize_ui_speeds(values: Iterable[int]) -> tuple[int, ...]:
    normalized: list[int] = []
    for value in values:
        normalized.append(max(0, min(10, int(value))))
    return tuple(dict.fromkeys(normalized))


def build_backend_speed_probe_plan(backend_name: object) -> dict[str, Any] | None:
    name = str(backend_name or "").strip().lower()
    if name != "ite8910":
        return None
    return _build_ite8910_speed_probe_plan()


def build_backend_speed_probe_plans(*, backends_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(backends_snapshot, dict):
        return []

    names: list[str] = []

    selected = str(backends_snapshot.get("selected") or "").strip().lower()
    if selected:
        names.append(selected)

    probes = backends_snapshot.get("probes")
    if isinstance(probes, list):
        for probe in probes:
            if not isinstance(probe, dict) or not bool(probe.get("available")):
                continue
            probe_name = str(probe.get("name") or "").strip().lower()
            if probe_name:
                names.append(probe_name)

    plans: list[dict[str, Any]] = []
    for name in dict.fromkeys(names):
        plan = build_backend_speed_probe_plan(name)
        if isinstance(plan, dict):
            plans.append(plan)
    return plans


def _build_ite8910_speed_probe_plan() -> dict[str, Any]:
    backend = Ite8910Backend()
    effect_name = ITE8910_SPEED_PROBE_EFFECT
    effect_func = backend.effects()[effect_name]
    kb = _ProbeKeyboard()
    kb_lock = RLock()
    ui_speeds = _normalize_ui_speeds(ITE8910_SPEED_PROBE_UI_SPEEDS)

    samples: list[dict[str, Any]] = []
    for ui_speed in ui_speeds:
        payload = build_hw_effect_payload(
            effect_name=effect_name,
            effect_func=effect_func,
            ui_speed=int(ui_speed),
            brightness=25,
            current_color=(255, 255, 255),
            hw_colors={},
            kb=kb,
            kb_lock=kb_lock,
            logger=backend_speed_probe_logger(),
        )
        payload_speed = None
        if isinstance(payload, dict) and payload.get("speed") is not None:
            payload_speed = int(payload.get("speed"))
        raw_speed = ite8910_protocol.raw_speed_from_effect_speed(payload_speed if payload_speed is not None else 0)
        samples.append(
            {
                "ui_speed": int(ui_speed),
                "payload_speed": payload_speed,
                "raw_speed": int(raw_speed),
                "raw_speed_hex": f"0x{int(raw_speed):02x}",
            }
        )

    return {
        "key": ITE8910_SPEED_PROBE_KEY,
        "label": "ITE8910 hardware speed probe",
        "backend": "ite8910",
        "effect_name": effect_name,
        "requested_ui_speeds": [int(value) for value in ui_speeds],
        "samples": samples,
        "expectation": "Higher UI speed values should look faster on ite8910.",
        "instructions": [
            "Switch the keyboard to the listed hardware effect using the tray or Settings window.",
            "Apply the listed UI speed values in order and watch whether each step is visually distinct.",
            "If multiple speeds appear identical or bunched together, record which values looked too close.",
        ],
        "observation_prompt": "Which speed steps looked identical, too close together, or clearly distinct?",
    }


def backend_speed_probe_logger():
    import logging

    return logging.getLogger(__name__)