#!/usr/bin/env python3
"""
KeyRGB Tuxedo GUI - Forked UI with ITE8291 backend
"""

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# Ensure we use our modified ite8291r3-ctl library
ite8291_path = os.path.join(REPO_ROOT, "ite8291r3-ctl")
if ite8291_path not in sys.path:
    sys.path.insert(0, ite8291_path)

# Add tuxedo-src to path
tuxedo_src = os.path.join(REPO_ROOT, "tuxedo-src")
if tuxedo_src not in sys.path:
    sys.path.insert(0, tuxedo_src)

# Launch UI
from ui import init  # noqa: E402

if __name__ == "__main__":
    init()
