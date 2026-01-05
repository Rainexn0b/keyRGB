from __future__ import annotations

from pathlib import Path

import tkinter as tk


def _candidate_logo_paths() -> list[Path]:
    paths: list[Path] = []

    # install.sh installs a user icon here.
    try:
        home = Path.home()
        paths.append(home / ".local/share/icons/hicolor/256x256/apps/keyrgb.png")
        paths.append(home / ".local/share/icons/keyrgb.png")
    except Exception:
        pass

    # Repo checkout (and editable installs) typically keep assets/ alongside src/.
    start = Path(__file__).resolve()
    for parent in [start] + list(start.parents):
        cand = parent / "assets" / "logo-keyrgb.png"
        if cand not in paths:
            paths.append(cand)

    return paths


def find_keyrgb_logo_path() -> Path | None:
    for p in _candidate_logo_paths():
        try:
            if p.is_file():
                return p
        except Exception:
            continue
    return None


def apply_keyrgb_window_icon(window: tk.Misc) -> None:
    """Best-effort: set KeyRGB icon for a Tk window.

    Uses the PNG logo from install.sh (preferred) or from repo assets.
    Safe to call on any Tk root/toplevel; does nothing on failure.
    """

    logo_path = find_keyrgb_logo_path()
    if logo_path is None:
        return

    try:
        from PIL import Image, ImageTk  # type: ignore

        img = Image.open(logo_path)
        # Small icon size keeps memory reasonable and looks fine in title bars.
        img = img.resize((64, 64))
        photo = ImageTk.PhotoImage(img)

        # Prevent garbage collection.
        setattr(window, "_keyrgb_icon_image", photo)

        iconphoto = getattr(window, "iconphoto", None)
        if callable(iconphoto):
            iconphoto(True, photo)
    except Exception:
        return
