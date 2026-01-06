from __future__ import annotations

import configparser
import os
import subprocess
from shutil import which


def _detect_theme_override() -> bool | None:
    override = os.environ.get("KEYRGB_THEME", "").strip().lower()
    if override in {"dark", "light"}:
        return override == "dark"
    return None


def _detect_gtk_theme_env() -> bool | None:
    gtk_theme = os.environ.get("GTK_THEME", "")
    if not gtk_theme:
        return None
    low = gtk_theme.lower()
    if ":dark" in low or low.endswith("dark") or "dark" in low:
        return True
    return None


def _detect_gsettings_color_scheme() -> bool | None:
    if not which("gsettings"):
        return None
    try:
        out = (
            subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.25,
            )
            .stdout.strip()
            .lower()
        )
        if "dark" in out:
            return True
        if "light" in out:
            return False
    except Exception:
        return None
    return None


def _read_kde_colorscheme_from_kreadconfig(kdeglobals: str) -> str | None:
    if not os.path.exists(kdeglobals):
        return None
    for tool in ("kreadconfig6", "kreadconfig5"):
        if not which(tool):
            continue
        try:
            out = (
                subprocess.run(
                    [
                        tool,
                        "--file",
                        kdeglobals,
                        "--group",
                        "General",
                        "--key",
                        "ColorScheme",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=0.25,
                )
                .stdout.strip()
                .lower()
            )
            if out:
                return out
        except Exception:
            continue
    return None


def _read_kde_colorscheme_from_ini(kdeglobals: str) -> str | None:
    if not os.path.exists(kdeglobals):
        return None
    try:
        in_general = False
        with open(kdeglobals, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_general = line.lower() == "[general]"
                    continue
                if not in_general:
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip().lower() == "colorscheme":
                    return value.strip().lower() or None
    except Exception:
        return None
    return None


def _detect_kde_prefers_dark() -> bool | None:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" not in desktop and "plasma" not in desktop:
        return None

    kdeglobals = os.path.expanduser("~/.config/kdeglobals")
    scheme = _read_kde_colorscheme_from_kreadconfig(kdeglobals) or _read_kde_colorscheme_from_ini(kdeglobals)
    if not scheme:
        return None
    return _kde_colorscheme_prefers_dark(scheme)


def detect_system_prefers_dark() -> bool | None:
    """Best-effort detection of whether the desktop prefers a dark color scheme.

    Returns:
        - True if the system appears to prefer dark
        - False if it appears to prefer light
        - None if unknown

    Notes:
        - Tk/ttk doesn't reliably inherit system dark/light preference across
          Linux desktop environments.
        - If this returns None, callers should fall back to the historical
          default to avoid surprising users.
    """

    providers = (
        _detect_theme_override,
        _detect_gtk_theme_env,
        _detect_gsettings_color_scheme,
        _detect_kde_prefers_dark,
    )

    for provider in providers:
        try:
            val = provider()
        except Exception:
            val = None
        if val is not None:
            return val

    return None


def _kde_colorscheme_prefers_dark(scheme: str) -> bool | None:
    """Infer whether a KDE color scheme is dark by reading its .colors file."""

    scheme = scheme.strip()
    if not scheme:
        return None

    luminance = _kde_colorscheme_background_luminance(scheme)
    if luminance is not None:
        # Threshold chosen to be conservative; typical dark schemes are well below 0.5.
        return luminance < 0.5

    low = scheme.lower()
    if "dark" in low:
        return True
    if low in {"breeze", "breezelight", "light"}:
        return False

    return None


def _kde_colorscheme_background_luminance(scheme: str) -> float | None:
    candidates = [
        os.path.expanduser(f"~/.local/share/color-schemes/{scheme}.colors"),
        f"/usr/share/color-schemes/{scheme}.colors",
        f"/usr/local/share/color-schemes/{scheme}.colors",
    ]

    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return None

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            parser.read_file(f)
    except Exception:
        return None

    # Prefer window background, then view background.
    for section in ("Colors:Window", "Colors:View"):
        if not parser.has_section(section):
            continue
        raw = parser.get(section, "BackgroundNormal", fallback="").strip()
        rgb = _parse_kde_rgb(raw)
        if rgb is None:
            continue
        r, g, b = rgb
        return _relative_luminance_srgb(r, g, b)

    return None


def _parse_kde_rgb(value: str) -> tuple[int, int, int] | None:
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) != 3:
        return None
    try:
        r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        return None
    return r, g, b


def _relative_luminance_srgb(r: int, g: int, b: int) -> float:
    """Compute relative luminance (WCAG) for sRGB 0..255."""

    def to_linear(c: float) -> float:
        c = c / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    rl = to_linear(float(r))
    gl = to_linear(float(g))
    bl = to_linear(float(b))
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
