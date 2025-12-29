# KeyRGB

KeyRGB is a Linux tray app + per-key editor for laptop keyboards driven by ITE 8291 / ITE8291R3-style controllers (common on TongFang rebrands). It focuses on being practical:

- System tray controls (effects, brightness, speed, off)
- Per-key coloring with a visual layout overlay
- A keymap calibrator that maps the keyboard's LED matrix to the visual keys
- Profile support (so different layouts/revisions can coexist)

If OpenRGB doesn't support your device (or is painful to operate), KeyRGB aims to be the missing tool.

## Status

- **Beta project**: versioning follows **0.x.y** tags until the first stable release.
- **Linux-only**: primarily developed/tested on Fedora-family distros (Fedora / Nobara).
- **Hardware-specific**: support depends on your keyboard controller + firmware.
- **Per-key requires calibration**: you must build a keymap before per-key effects work.

## Quickstart

### Install

On Fedora (including Nobara), the recommended path is:

```bash
./install.sh
```

Notes:

- The installer can be run from any working directory (it will switch to the repo root internally).
- It installs a desktop app launcher (so you can start KeyRGB from your app menu) and an autostart entry (so it starts on login).
- TUXEDO Control Center (TCC) integration dependencies are optional; the installer will ask.

Docs:

- Fedora / step-by-step from a blank install: [docs/usage/usage.md](docs/usage/usage.md)
- Fedora / RPM packaging: [packaging/rpm/README.md](packaging/rpm/README.md)
- Development / Tongfang keyboard support roadmap: [docs/developement/tongfang/00-index.md](docs/developement/tongfang/00-index.md)

On other distros, install the Python dependencies + ensure the udev rule is present (see the docs above).

Or install from the repo (useful for development):

```bash
python3 -m pip install --user -e .
```

### Run

Start the tray app:

```bash
keyrgb
```

Dev/repo mode (runs attached to your terminal):

```bash
./keyrgb
```

Open the per-key editor:

```bash
keyrgb-perkey
```

## Backend selection (multi-vendor)

KeyRGB is moving toward a multi-backend architecture so additional keyboard controllers/vendors can be supported over time.

- Auto select (default): no env vars needed.
- Force a specific backend: set `KEYRGB_BACKEND`.

Examples:

```bash
KEYRGB_BACKEND=auto keyrgb
KEYRGB_BACKEND=ite8291r3 keyrgb
```

Notes:

- Today, `ite8291r3` is the primary backend.
- If no backend is available, the tray/GUI should still launch (you’ll just have no hardware control).

## Development note: package layout

This repository currently ships its Python package as `src.*` (e.g. `src.gui.tray`).
It works, but it’s non-standard; a future “breaking cleanup” may rename it to a proper `keyrgb.*` package.
Until then, avoid relying on `src.*` imports as a stable external API.

## How per-key works

Most of these controllers expose a fixed LED matrix (often 6×21). The physical key at `(row, col)` is device-specific.

KeyRGB solves this by calibration:

1. Run the calibrator.
2. It lights one matrix cell at a time.
3. You click the corresponding key on the on-screen image.
4. Save the keymap.

After calibration, the per-key editor and effects use that mapping.

## Profiles

Profiles live under:

`~/.config/keyrgb/profiles/<profile>/`

Each profile groups:

- The keymap
- Global overlay alignment tweaks
- Per-key overlay tweaks
- Per-key colors

Use the **Profiles** section in the per-key editor to Activate/Save/Delete.

## Hardware support

This project is currently focused on ITE 8291 / ITE8291R3 based keyboards.

- Typical USB ID: `048d:600b`
- Typical matrix: 6×21

Support is device/firmware dependent. If you want to contribute a new laptop revision, see [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Troubleshooting

- **No tray icon / nothing happens**: run `keyrgb` from a terminal and check logs.
- **Permission denied / cannot open device**: ensure the udev rule is installed and replug/reboot.
- **Effects “fight” or flicker**: stop other RGB tools (`openrgb`, Tuxedo tools) so there is a single owner.
- **Per-key does nothing**: you need a keymap. Open `keyrgb-perkey` and click **Run Keymap Calibrator**.

Diagnostics (for bug reports):

```bash
keyrgb-diagnostics
```

## Settings

The tray menu includes a **Settings** entry which opens a small GUI for:

- **Power Management**: turn keyboard LEDs off/on on suspend/resume and lid close/open.
- **Autostart**:
	- **Start lighting on launch** (KeyRGB behavior at startup)
	- **Start KeyRGB on login** (OS session autostart via `~/.config/autostart/keyrgb.desktop`)

If you quit the tray during a session, you can re-open it from your desktop app menu by searching for **KeyRGB**.

## Getting your hardware supported

If KeyRGB doesn’t control your keyboard yet (or behaves oddly), please open a GitHub issue and include the information below.
This is the fastest way to let us map your laptop revision to the right backend/quirks.

Open an issue here:

- [GitHub Issues (new issue)](../../issues/new/choose)

Choose **Hardware support / diagnostics** for new laptop models, or **Bug report** for problems on already-supported hardware.

### 1) Run diagnostics

Run:

```bash
keyrgb-diagnostics
```

Paste the full JSON output into the issue.

What it includes (read-only):

- DMI identity (`sys_vendor`, `product_name`, `board_name`)
- Candidate sysfs LED nodes (keyboard backlight paths)
- USB IDs (best-effort enumeration)

### 2) Run KeyRGB with debug logs

```bash
KEYRGB_DEBUG=1 keyrgb
```

Then:

- Describe what you clicked (tray menu items, GUI actions)
- Paste any errors/warnings from the terminal

### 3) If USB is involved, also paste this

```bash
lsusb | grep -i "048d:" || true
```

### 4) What to mention in plain English

- Laptop brand + model name you bought (e.g. WootBook / Tuxedo / XMG)
- What works vs what doesn’t (brightness, effects, per-key)
- Any quirks (e.g. “after resume it switches to rainbow and ignores settings”)

### Privacy note

`keyrgb-diagnostics` does not include usernames or home directory paths.
If you still prefer to redact, you can replace DMI values with `REDACTED` while keeping their *presence* and structure.

More troubleshooting and setup details are in [docs/usage/usage.md](docs/usage/usage.md).

## Optional dependencies

- `PyQt6` is used for optional slider dialogs in the tray UI. KeyRGB still runs without it.
	- Install it with `python3 -m pip install --user "PyQt6>=6.10.0"` or `python3 -m pip install --user -e ".[qt]"`.

## Legacy / archived

This repo includes some older experiments and patches under [PRs](PRs).

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
