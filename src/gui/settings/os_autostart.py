from __future__ import annotations

from pathlib import Path


def autostart_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "keyrgb.desktop"


def detect_os_autostart_enabled() -> bool:
    try:
        return autostart_desktop_path().exists()
    except Exception:
        return False


def set_os_autostart(enabled: bool) -> None:
    desktop_path = autostart_desktop_path()
    if not enabled:
        try:
            desktop_path.unlink(missing_ok=True)
        except Exception:
            # If removal fails, surface as error.
            raise
        return

    desktop_path.parent.mkdir(parents=True, exist_ok=True)

    # Use the installed console script entrypoint.
    desktop_contents = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=KeyRGB\n"
        "Comment=Keyboard RGB tray\n"
        "Exec=keyrgb\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )

    desktop_path.write_text(desktop_contents, encoding="utf-8")
