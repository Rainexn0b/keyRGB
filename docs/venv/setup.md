# Virtual environment setup

This guide covers creating and maintaining the development venv for KeyRGB.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python >= 3.10 | 3.12 or 3.14 recommended |
| PyGObject (`gi`) | Must be installed system-wide |
| AyatanaAppIndicator3 / AppIndicator3 | Needed for proper tray integration on GTK desktops |

### Install system dependencies

**Fedora / Nobara**

```bash
sudo dnf install python3-gobject libayatana-appindicator libayatana-appindicator-gtk3
```

**CachyOS / Arch**

```bash
sudo pacman -S --needed python-gobject libayatana-appindicator
```

**Ubuntu / Debian**

```bash
sudo apt install python3-gi gir1.2-appindicator3-0.1
# or for Ayatana:
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

PyGObject should come from the system package manager, not from `pip`.

## Create the venv

```bash
python3 -m venv .venv
```

Expose system `gi` into the venv so `pystray` can use AppIndicator:

```bash
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SYS_SITE=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
ln -s "${SYS_SITE}/gi" ".venv/lib/python${PY_VER}/site-packages/gi"
```

Install the project in editable mode:

```bash
.venv/bin/python -m pip install -e '.[qt,dev]'
```

Fish users should prefer `.venv/bin/python ...` directly instead of sourcing the POSIX activation script.

## Verify the venv

```bash
.venv/bin/python -c "import gi; print('gi ok')"
.venv/bin/python -c "from src.tray.integrations.runtime import _gi_is_working; print(_gi_is_working())"
```

## Common commands

```bash
.venv/bin/python -m pytest src/tests/
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m src.tray.entrypoint
```

## Rebuild a broken venv

```bash
rm -rf .venv
python3 -m venv .venv
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SYS_SITE=$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
ln -s "${SYS_SITE}/gi" ".venv/lib/python${PY_VER}/site-packages/gi"
.venv/bin/python -m pip install -e '.[qt,dev]'
```