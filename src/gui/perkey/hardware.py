from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _try_import_backend() -> tuple[Any, int, int]:
    """Import the ite8291 backend.

    Returns (get_fn_or_none, num_rows, num_cols).

    This supports both:
    - installed dependency (`ite8291r3_ctl`)
    - vendored repo fallback (`./ite8291r3-ctl`)
    """

    try:
        from ite8291r3_ctl.ite8291r3 import get as _get, NUM_ROWS, NUM_COLS

        return _get, int(NUM_ROWS), int(NUM_COLS)
    except Exception:
        pass

    # Repo fallback if dependency wasn't installed.
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    vendored = repo_root / "ite8291r3-ctl"
    if vendored.exists():
        sys.path.insert(0, str(vendored))

    try:
        from ite8291r3_ctl.ite8291r3 import get as _get, NUM_ROWS, NUM_COLS

        return _get, int(NUM_ROWS), int(NUM_COLS)
    except Exception:
        return None, 6, 21


_get, NUM_ROWS, NUM_COLS = _try_import_backend()


def get_keyboard():
    """Return a keyboard instance if the backend is available."""

    if _get is None:
        return None
    try:
        return _get()
    except Exception:
        return None
