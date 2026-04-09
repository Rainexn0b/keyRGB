## Issue 6: Tray icon fails to appear on GNOME 50 with AppIndicator extension

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/6

Status: Investigated and fixed in working tree.

---

## Report summary

| Field | Value |
|---|---|
| Reporter | ajcoli3 |
| Version | v0.21.5 AppImage |
| OS | CachyOS |
| Desktop | GNOME 50 (Wayland) |
| Kernel | 6.19.11-1 |
| Hardware | Maingear Vector Pro 2 |
| GNOME extension | AppIndicator and kStatusNotifierItem Support |

**Observed:** The tray icon does not appear after install. Other tray icons (1Password, Cachy-Update) appear correctly. Keyboard lighting works (F5/F6 keys), so the backend is functional.

**Not observed:** No log output was provided by the reporter. Other running RGB tools (OpenRGB, TCC) were stopped before reproduction.

---

## Root-cause analysis

### GNOME does not support the legacy XEmbed system tray protocol

GNOME Shell has not included a native XEmbed system tray since GNOME 3.26. Apps relying on the old protocol (`_NET_SYSTEM_TRAY_S0` XEmbed ICCCM mechanism) are simply invisible in GNOME — the compositor has no slot to embed them.

`pystray`'s `gtk` backend creates a `GtkStatusIcon`, which:

- Was deprecated in GTK 3.14.
- Was removed in GTK 4.
- Uses the XEmbed tray protocol.
- Is therefore **invisible on GNOME Shell** regardless of what extensions are installed.

### The AppIndicator extension requires the SNI (StatusNotifierItem) protocol

The "AppIndicator and kStatusNotifierItem Support" GNOME Shell extension implements the `org.kde.StatusNotifierItem` / `org.freedesktop.StatusNotifierItem` D-Bus protocol (SNI). This is the same protocol used by:

- The `appindicator` pystray backend.
- 1Password's Linux tray icon.
- System-level tools like `update-notifier`, `nm-applet` (when using the SNI path).

The extension has **no effect on** `GtkStatusIcon`-based tray icons because those go through a completely different mechanism (X11 XEmbed, not D-Bus SNI).

### pystray backend selection in keyRGB

`src/tray/integrations/runtime.py`, `_auto_backend_candidates()`:

```
KDE Wayland  →  appindicator (first) → gtk → xorg
Everything else  →  gtk (first) → xorg → appindicator
```

GNOME (X11 or Wayland) falls into the "everything else" path, which tries `gtk` first. Since `gtk`/`GtkStatusIcon` is invisible on modern GNOME, the icon never appears even though the `appindicator` candidate (which would work) is third in the fallback list — and pystray does not fall back automatically based on visibility, only on import/init failures.

### Why KDE Wayland is already fixed but GNOME is not

The KDE Wayland special-case was added earlier because KDE's compositor also requires SNI (not XEmbed) for Wayland tray icons. The same logic applies to GNOME, but GNOME was never added to the detection path.

### Why other apps work

1Password, Cachy-Update, and similar apps either:

- Use the `libappindicator` / `libayatana-appindicator` library directly (which uses SNI), or
- Are Electron/Qt apps that use their own SNI implementations.

They do not go through `GtkStatusIcon`.

---

## Affected environments

All GNOME sessions with the AppIndicator/SNI extension installed, including:

- GNOME on Wayland (all distros: Ubuntu, Fedora, CachyOS/Arch, etc.)
- GNOME on X11 (GNOME Shell has not embedded XEmbed trays since ~3.26)

GNOME is the second-most common Linux desktop environment, and CachyOS ships GNOME as an option.

Detection signal: `XDG_CURRENT_DESKTOP` contains `GNOME` (or `gnome`), or `DESKTOP_SESSION` contains `gnome`.

---

## Fix

Add `_is_gnome_session()` detection to `src/tray/integrations/runtime.py` and adjust `_auto_backend_candidates()` to place `appindicator` first for GNOME sessions — matching the existing KDE Wayland path.

**Before:**
```python
def _auto_backend_candidates(*, gi_working: bool) -> list[tuple[str, str]]:
    if not gi_working:
        return [("xorg", "xorg (auto)")]
    if _is_kde_wayland_session():
        return [
            ("appindicator", "appindicator (auto-kde-wayland)"),
            ("gtk", "gtk (appindicator fallback)"),
            ("xorg", "xorg (gtk fallback)"),
        ]
    return [
        ("gtk", "gtk (auto)"),
        ("xorg", "xorg (gtk fallback)"),
        ("appindicator", "appindicator (xorg fallback)"),
    ]
```

**After:**
```python
def _is_gnome_session() -> bool:
    current_desktop = str(os.environ.get("XDG_CURRENT_DESKTOP") or "").strip().lower()
    desktop_session = str(os.environ.get("DESKTOP_SESSION") or "").strip().lower()
    return "gnome" in current_desktop or "gnome" in desktop_session


def _auto_backend_candidates(*, gi_working: bool) -> list[tuple[str, str]]:
    if not gi_working:
        return [("xorg", "xorg (auto)")]
    if _is_kde_wayland_session():
        return [
            ("appindicator", "appindicator (auto-kde-wayland)"),
            ("gtk", "gtk (appindicator fallback)"),
            ("xorg", "xorg (gtk fallback)"),
        ]
    if _is_gnome_session():
        return [
            ("appindicator", "appindicator (auto-gnome)"),
            ("gtk", "gtk (appindicator fallback)"),
            ("xorg", "xorg (gtk fallback)"),
        ]
    return [
        ("gtk", "gtk (auto)"),
        ("xorg", "xorg (gtk fallback)"),
        ("appindicator", "appindicator (xorg fallback)"),
    ]
```

**Scope:** `src/tray/integrations/runtime.py` only. No changes to backends, UI, or installer.

**Required GNOME-side precondition (same as before this fix):** The "AppIndicator and kStatusNotifierItem Support" GNOME Shell extension must be installed and enabled. Without it, `appindicator` will import successfully but the SNI icon will not be rendered by the compositor. This is documented in the README.

---

## User workaround (before fix lands)

Set `PYSTRAY_BACKEND=appindicator` in the environment before launching keyRGB:

```bash
PYSTRAY_BACKEND=appindicator keyrgb
```

Or add to `~/.config/keyrgb/env` (if the AppImage launcher respects it) or as a systemd user unit override.

---

## Open questions

- No diagnostic log was provided. The `KEYRGB_DEBUG=1` path would confirm which pystray backend was selected and whether any import errors occurred.
- The reporter has a Maingear Vector Pro 2. It is a Tongfang rebrand; the keyboard backend path is unrelated to the tray icon issue.

---

## Files changed

- `src/tray/integrations/runtime.py` — add `_is_gnome_session()`, update `_auto_backend_candidates()`
- `tests/tray/integrations/test_tray_integrations_runtime_more_unit.py` — add GNOME detection tests and candidate-ordering test
- `CHANGELOG.md` — user-visible fix note
