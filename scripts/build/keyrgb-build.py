#!/usr/bin/env python3
"""Compatibility wrapper.

KeyRGB's Python build runner lives in the `buildpython/` package.

Keep this file so any existing docs/aliases like:
  `python3 scripts/build/keyrgb-build.py --profile=ci`
continue to work.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Ensure repo-root imports work when running as a script.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from buildpython.core.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
