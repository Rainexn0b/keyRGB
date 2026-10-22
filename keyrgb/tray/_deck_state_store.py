"""Small state-store helpers for the deck commit pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from keyrgb.tray.deck_state import DeckState
from keyrgb.tray.idle_power_state import ensure_tray_idle_power_state, is_dim_temp_active

if TYPE_CHECKING:
    from keyrgb.tray.protocols import IdlePowerTrayProtocol


def _store_deck_state(tray: IdlePowerTrayProtocol, state: DeckState) -> None:
    """Publish the transient phase; stable state derives from owned causes."""
    try:
        ensure_tray_idle_power_state(tray)._restoring = state is DeckState.RESTORING
    except (AttributeError, TypeError):
        return


def _completed_lit_state(tray: IdlePowerTrayProtocol) -> DeckState:
    return DeckState.DIM_TEMP if is_dim_temp_active(tray) else DeckState.LIT
