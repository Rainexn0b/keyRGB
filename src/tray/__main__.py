"""`python -m src.tray` entrypoint.

Kept for convenient local development runs from the repository root.
For installed usage, prefer the `keyrgb` console script.
"""

from __future__ import annotations

from .entrypoint import main


if __name__ == "__main__":
    main()
