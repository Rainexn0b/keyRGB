# Virtual environment setup

This guide covers creating and maintaining the development venv for KeyRGB.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.10 | 3.12 or 3.14 recommended |
| PyGObject (`gi`) | Must be installed system-wide (see below) |
| AyatanaAppIndicator3 / AppIndicator3 | For proper tray icon on GTK desktops |

### Install system dependencies

**Fedora / Nobara (primary target)**
```bash
sudo dnf install python3-gobject libayatana-appindicator libayatana-appindicator-gtk3
```

**CachyOS / Arch**
```bash
sudo pacman -S --needed python-gobject libayatana-appindicator
```

**Ubuntu / Debian (experimental)**
```bash
sudo apt install python3-gi gir1.2-appindicator3-0.1
# or for Ayatana:
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

> PyGObject must be the **system** package, not a pip package. `pip install PyGObject`
> builds the C extension against system headers and may produce a broken module if the
> system GTK library version differs.

---

## Create the venv (isolated, recommended)

```bash
# 1. Create isolated venv (no system site-packages)
python3 -m venv .venv

# 2. Expose system gi (PyGObject) so pystray can use AppIndicator → transparent tray icon
#    Adjust the pythonX.Y path to match your Python version (check: python3 --version)
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SYS_SITE=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
ln -s "${SYS_SITE}/gi" ".venv/lib/python${PY_VER}/site-packages/gi"

# 3. Install the package in editable mode with all dev and Qt extras
.venv/bin/python -m pip install -e '.[qt,dev]'
```

### Why symlink gi instead of using system-site-packages?

Using `python3 -m venv --system-site-packages .venv` also works but pulls every
installed system package into pip's view, causing unrelated `pip check` failures
(e.g. from `glances`, `moddb`, or other global tools).

Symlinking only `gi` gives the venv access to PyGObject without any of that noise.

### Why is gi needed at all?

pystray's backend selection order on Linux is:

1. `appindicator` — renders via StatusNotifierItem/AppIndicator, respects DE theming,
   produces a properly transparent icon on KDE Plasma (Wayland and X11).
2. `gtk` — GTK3 StatusIcon (deprecated, still usable).
3. `xorg` — raw X11 XEmbed. Falls back to this when `gi` is absent.

The Xorg backend paints RGBA icon data onto an opaque X window. On modern compositors
(KWin Wayland, GNOME, etc.) this shows as a **solid grey/white square** rather than a
transparent tray icon.

---

## Verify the venv

```bash
# gi accessible
.venv/bin/python -c "import gi; print('gi ok, require_version:', hasattr(gi, 'require_version'))"

# AyatanaAppIndicator accessible
.venv/bin/python -c "
import gi
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import AyatanaAppIndicator3
print('AyatanaAppIndicator3 ok')
"

# keyrgb imports cleanly
.venv/bin/python -c "from src.tray.integrations.runtime import _gi_is_working; print('_gi_is_working():', _gi_is_working())"
# Expected: _gi_is_working(): True
```

---

## Running tools from the venv

> **fish shell users:** the generated `activate` script uses POSIX-only syntax.
> Use `.venv/bin/python` directly instead of `source .venv/bin/activate`.

```bash
# Run tests
.venv/bin/python -m pytest src/tests/

# Run the full CI gate
.venv/bin/python -m buildpython --profile=ci

# Run the full local quality gate (includes black formatting)
.venv/bin/python -m buildpython --profile=full --with-black

# Run the tray app directly
.venv/bin/python -m src.tray.entrypoint
```

---

## Rebuild a broken venv from scratch

```bash
rm -rf .venv

python3 -m venv .venv

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SYS_SITE=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
ln -s "${SYS_SITE}/gi" ".venv/lib/python${PY_VER}/site-packages/gi"

.venv/bin/python -m pip install -e '.[qt,dev]'
```

---

## Common problems

### Tray icon shows as a solid square

`gi` is not accessible from the venv. pystray has fallen back to the Xorg backend.

```bash
.venv/bin/python -c "import gi; print('ok')"
```

If this fails with `ModuleNotFoundError`, re-run step 2 of the setup to add the `gi`
symlink.

### `ModuleNotFoundError: No module named 'PyQt6'`

PyQt6 was not installed. Re-run pip with the `qt` extra:

```bash
.venv/bin/python -m pip install -e '.[qt,dev]'
```

### `pip check` reports broken requirements

Usually caused by unrelated system-wide packages being visible. Confirm the venv was
**not** created with `--system-site-packages`.

```bash
cat .venv/pyvenv.cfg | grep include-system
# Expected: include-system-site-packages = false
```

If it shows `true`, rebuild the venv using the instructions above.

### `ImportError: libtk8.6.so` (Arch/CachyOS only)

The `tk` package is not installed:

```bash
sudo pacman -S tk
```
