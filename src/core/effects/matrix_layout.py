from __future__ import annotations

"""Canonical effect-grid dimensions.

Software effects, reactive rendering, fades, and tray-icon mosaics use a
stable logical keyboard matrix that is intentionally backend-agnostic.

This is separate from backend runtime selection. Hardware backends may expose
their own device dimensions for probing or transport purposes, but the software
effects stack should not depend on hidden backend selection at import time.
"""

from typing import Final


NUM_ROWS: Final[int] = 6
NUM_COLS: Final[int] = 21