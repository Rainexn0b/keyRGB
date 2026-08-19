"""Pure power-source idle-guard decisions (no tray I/O).

Extracted for WS2 orchestration purity: classify AC transitions and guard
windows without mutating poller state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerSourceGuardUpdate:
    """Result of observing an AC/battery reading against prior guard state."""

    last_on_ac_power: bool | None
    last_power_source_change_at: float
    reset_sensitive_idle_state: bool


def power_source_idle_guard_active(
    *,
    now: float,
    last_power_source_change_at: float,
    suppression_s: float,
) -> bool:
    changed_at = float(last_power_source_change_at or 0.0)
    if changed_at <= 0.0:
        return False
    return (float(now) - changed_at) < float(suppression_s)


def plan_power_source_guard_update(
    *,
    on_ac_power: bool | None,
    last_on_ac_power: bool | None,
    last_power_source_change_at: float,
    now: float,
) -> PowerSourceGuardUpdate | None:
    """Return a state update when an AC reading should advance guard state.

    Returns ``None`` when ``on_ac_power`` is unknown (no update).
    """

    if on_ac_power is None:
        return None

    on_ac = bool(on_ac_power)
    if last_on_ac_power is None:
        return PowerSourceGuardUpdate(
            last_on_ac_power=on_ac,
            last_power_source_change_at=float(last_power_source_change_at or 0.0),
            reset_sensitive_idle_state=False,
        )

    if on_ac == bool(last_on_ac_power):
        return PowerSourceGuardUpdate(
            last_on_ac_power=bool(last_on_ac_power),
            last_power_source_change_at=float(last_power_source_change_at or 0.0),
            reset_sensitive_idle_state=False,
        )

    return PowerSourceGuardUpdate(
        last_on_ac_power=on_ac,
        last_power_source_change_at=float(now),
        reset_sensitive_idle_state=True,
    )
