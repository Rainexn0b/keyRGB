from __future__ import annotations

import os
import sys
from pathlib import Path


def load_ite_dimensions() -> tuple[int, int]:
    """Load ITE keyboard matrix dimensions.

    Prefers the vendored `ite8291r3-ctl` checkout when present, unless
    `KEYRGB_USE_INSTALLED_ITE=1` is set.

    Falls back to a common default if anything goes wrong.
    """

    try:
        repo_root = Path(__file__).resolve().parents[2]
        vendored = repo_root / "ite8291r3-ctl"
        if vendored.exists() and os.environ.get("KEYRGB_USE_INSTALLED_ITE") != "1":
            sys.path.insert(0, str(vendored))

        from ite8291r3_ctl.ite8291r3 import NUM_ROWS as r, NUM_COLS as c

        return int(r), int(c)
    except Exception:
        return 6, 21
