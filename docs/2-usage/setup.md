# Local setup

Use the project venv for every Python command. Distro `python` can pull host
packages (including numpy stubs) that fail Type Check against KeyRGB's 3.10
mypy floor.

```bash
.venv/bin/python -m buildpython
```

## System packages

PyGObject (`gi`) must come from the distro, not pip. The venv Python minor
version must match that `_gi` extension.

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
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
```

## Venv

Python >= 3.10. Expose distro site-packages so `gi` loads:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[dev]'
```

With `uv`, pin the same distro Python:

```bash
uv venv --system-site-packages --python /usr/bin/python3 .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Do not symlink `gi` across Python minor versions (a 3.13 venv cannot load a
3.14 `_gi` module).

Fish: call `.venv/bin/python ...` directly; skip POSIX `activate`.

## Check

```bash
.venv/bin/python -c "import gi; print('gi ok')"
.venv/bin/python -m keyrgb.tray.entrypoint
```

## Rebuild

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e '.[dev]'
```
