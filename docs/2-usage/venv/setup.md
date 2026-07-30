# Virtual environment setup

This guide covers creating and maintaining the development venv for KeyRGB.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python >= 3.10 | 3.12 or 3.14 recommended |
| PyGObject (`gi`) | Optional tray dependency for the GTK and AppIndicator backends |
| AyatanaAppIndicator3 / AppIndicator3 | Needed when the session prefers the AppIndicator tray backend, such as KDE Plasma on Wayland |

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

Create the venv from the distro Python and expose distro-managed packages. This
is important for PyGObject: its compiled `_gi` extension must match the Python
minor version used by the venv.

```bash
python3 -m venv --system-site-packages .venv
```

For `uv`, select the same distro Python explicitly:

```bash
uv venv --system-site-packages --python /usr/bin/python3 .venv
```

Do not symlink `gi` from a different Python minor version. For example, a
Python 3.13 `uv` venv cannot load CachyOS/Arch's Python 3.14 `_gi` extension.

Install the project in editable mode:

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

Fish users should prefer `.venv/bin/python ...` directly instead of sourcing the POSIX activation script.

## Verify the venv

```bash
.venv/bin/python -c "import gi; print('gi ok')"
.venv/bin/python -c "from src.tray.integrations.runtime import _gi_is_working; print(_gi_is_working())"
```

## Common commands

```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m src.tray.entrypoint
```

## Rebuild a broken venv

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[dev]'
```
