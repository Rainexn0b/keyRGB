# KeyRGB

KeyRGB is a Linux tray app + per-key editor for laptop keyboards driven by ITE 8291 / ITE8291R3-style controllers (common on TongFang rebrands). It focuses on being practical:

- System tray controls (effects, brightness, speed, off)
- Per-key coloring with a visual layout overlay
- A keymap calibrator that maps the keyboard's LED matrix to the visual keys
- Profile support (so different layouts/revisions can coexist)

If OpenRGB doesn't support your device (or is painful to operate), KeyRGB aims to be the missing tool.

## Quickstart

### Install

```bash
./install.sh
```

Fedora / RPM users: see `packaging/rpm/README.md` for `dnf install` instructions.

Or install from the repo (useful for development):

```bash
python3 -m pip install --user -e .
```

### Run

Start the tray app:

```bash
./keyrgb
```

Or if installed:

```bash
keyrgb
```

Open the per-key editor:

```bash
keyrgb-perkey
```

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

Support is device/firmware dependent. If you want to contribute a new laptop revision, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Troubleshooting

- **No tray icon / nothing happens**: run `keyrgb` from a terminal and check logs.
- **Permission denied / cannot open device**: ensure the udev rule is installed and replug/reboot.
- **Effects “fight” or flicker**: stop other RGB tools (`openrgb`, Tuxedo tools) so there is a single owner.
- **Per-key does nothing**: you need a keymap. Open `keyrgb-perkey` and click **Run Keymap Calibrator**.

## Optional dependencies

- `PyQt6` is used for optional slider dialogs in the tray UI. KeyRGB still runs without it.
	- Install it with `python3 -m pip install --user "PyQt6>=6.10.0"` or `python3 -m pip install --user -e ".[qt]"`.

## Legacy / archived

This repo includes some older experiments and patches under [PRs](PRs).

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
