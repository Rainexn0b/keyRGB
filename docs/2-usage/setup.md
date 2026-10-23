# Local setup

Use the project venv for every Python command. Distro `python` can pull host
packages (including numpy stubs) that fail Type Check against KeyRGB's 3.11
mypy floor.

```bash
.venv/bin/python -m buildpython
```

## System packages

For local development, prefer distro PyGObject (`gi`). The venv Python minor
version must match that `_gi` extension and be at least 3.11. Do not use Ubuntu
22.04's CPython 3.10 GI extension with a newer interpreter; use the AppImage or
build GI bindings for that interpreter instead.

Release AppImages still build on Ubuntu 22.04 (glibc 2.35), using
`actions/setup-python` Python 3.11 and source-built PyGObject 3.50.2 plus pycairo
1.25.1 for a matching ABI. They do not use Jammy's distro CPython 3.10 GI module.

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

Python >= 3.11 and Pillow >= 13.0.0 (installed by the project dependency below).
With a matching distro Python >= 3.11, expose distro site-packages so `gi` loads:

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
