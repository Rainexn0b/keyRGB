from __future__ import annotations

import os
import sys
from pathlib import Path


def _prefer_vendored_ite() -> None:
    """Prefer the vendored ite8291r3-ctl checkout when present.

    This repo carries local modifications/pending PRs. Allow opting into the
    installed dependency with `KEYRGB_USE_INSTALLED_ITE=1`.

    If an installed `ite8291r3_ctl` was already imported earlier in the same
    interpreter session, force a re-import from the vendored path.
    """

    if os.environ.get("KEYRGB_USE_INSTALLED_ITE") == "1":
        return

    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "ite8291r3-ctl",
        repo_root / "vendor" / "ite8291r3-ctl",
    ]
    vendored = next((p for p in candidates if p.exists()), None)
    if vendored is None:
        return

    sys.path.insert(0, str(vendored))

    existing = sys.modules.get("ite8291r3_ctl")
    try:
        existing_file = Path(getattr(existing, "__file__", "")).resolve()
    except Exception:
        existing_file = None

    if existing_file and vendored not in existing_file.parents:
        for name in list(sys.modules.keys()):
            if name == "ite8291r3_ctl" or name.startswith("ite8291r3_ctl."):
                sys.modules.pop(name, None)


_prefer_vendored_ite()

from ite8291r3_ctl.ite8291r3 import NUM_COLS, NUM_ROWS, colors as hw_colors, effects as hw_effects, get

__all__ = ["get", "hw_effects", "hw_colors", "NUM_ROWS", "NUM_COLS"]
