# KeyRGB

KeyRGB is a lightweight Linux tray app and per-key editor for laptop keyboard lighting. It serves as a practical, focused alternative to OpenRGB for supported devices.

## Supported backends

- **USB (ITE 8291 / 8291R3 family)**: common on TongFang rebrands (XMG, Tuxedo, Wootbook, Eluktronics). Supports per-key RGB.
- **Sysfs LED**: universal Linux backend (brightness-only or basic RGB, depending on kernel drivers).

## Status

- **Beta**: versioning follows **0.x.y**.
- Developed primarily for Fedora / Nobara.
- Support depends entirely on your specific keyboard controller and firmware.

## Screenshots

<table>
	<tr>
		<td width="50%">
			<b>Tray Menu (Effects)</b><br>
			<img src="assets/screenshots/trayeffects.png" alt="Tray menu effects">
		</td>
		<td width="50%">
			<b>Power Management</b><br>
			<img src="assets/screenshots/traypp.png" alt="Tray power menu">
		</td>
	</tr>
	<tr>
		<td width="50%">
			<b>Per-Key Editor</b><br>
			<img src="assets/screenshots/perkeyux.png" alt="Per-key editor">
		</td>
		<td width="50%">
			<b>Settings</b><br>
			<img src="assets/screenshots/settings.png" alt="Settings UI">
		</td>
	</tr>
	<tr>
		<td width="50%">
			<b>Tray Menu (Brightness)</b><br>
			<img src="assets/screenshots/traybo.png" alt="Tray menu brightness">
		</td>
		<td width="50%">
			<b>RAM / CPU Usage</b><br>
			<img src="assets/screenshots/ramusage.png" alt="RAM and CPU usage">
		</td>
	</tr>
</table>

## Quickstart

### Install

On Fedora / Nobara (recommended):

```bash
./install.sh
```

This installs the AppImage to `~/.local/bin/keyrgb`, sets up the desktop launcher, and installs necessary udev rules for hardware access.

Docs:

- Step-by-step from a blank install: [docs/usage/usage.md](docs/usage/usage.md)
- Architecture / TongFang support roadmap: [docs/architecture/tongfang/00-index.md](docs/architecture/tongfang/00-index.md)

### Uninstall

```bash
# Interactive removal
./uninstall.sh

# Non-interactive (scripted)
./uninstall.sh --yes --remove-appimage
```

### Run

| Command | Description |
| --- | --- |
| `keyrgb` | Start the tray app (background). |
| `./keyrgb` | Run attached to terminal (dev mode). |
| `keyrgb-perkey` | Open the per-key editor. |
| `keyrgb-diagnostics` | Print hardware diagnostics JSON. |

## Configuration

### Settings and autostart

Access **Settings** via the tray menu to configure:

- **Power Management**: toggle LEDs on Suspend/Resume or Lid Close/Open.
- **Screen Dim Sync**: sync keyboard brightness with screen dimming (KDE Plasma / Wayland).
- **Autostart**: enable “Start KeyRGB on login”.

### Profiles

Profiles are stored in:

`~/.config/keyrgb/profiles/`

Each profile contains the keymap (calibration), global overlay tweaks, and per-key color data. Manage these via the Per-Key Editor.

### Per-key calibration

Most supported controllers use a fixed LED matrix (e.g., 6×21). To map this to your physical layout:

1. Open `keyrgb-perkey`.
2. Click **Run Keymap Calibrator**.
3. Click the corresponding key on-screen as each physical LED lights up.
4. Save the keymap.

## Troubleshooting

| Issue | Solution |
| --- | --- |
| No tray icon | Run `keyrgb` from a terminal to see errors. Check if the system tray extension is enabled (GNOME). |
| Permission denied | Ensure udev rules are installed. Try replugging the device or rebooting. |
| Flickering effects | Ensure other tools (OpenRGB, TCC) are not running. KeyRGB needs exclusive access. |
| Per-key not working | You likely need to run the Keymap Calibrator first. |

## Advanced usage

### Installer arguments

| Argument | Meaning |
| --- | --- |
| `--appimage` | Download AppImage (default). |
| `--pip` | Install via `pip --user` (dev/editable). |
| `--clone` | Clone repo and install via pip (source). |
| `--version <tag>` | Install specific tag (e.g. `v0.9.2`). |

### Environment variables

| Variable | Usage |
| --- | --- |
| `KEYRGB_BACKEND` | Force backend: `auto` (default), `ite8291r3`, or `sysfs-leds`. |
| `KEYRGB_DEBUG=1` | Enable verbose debug logging for bug reports. |
| `KEYRGB_TK_SCALING` | Float override for UI scaling (fixes High-DPI quirks). |

## Hardware support and contributing

If KeyRGB detects your device but behaves oddly, or if you have a new laptop model (TongFang/Clevo/etc.), please help us support it.

1) Run diagnostics:

```bash
keyrgb-diagnostics
```

2) Open an issue:

- https://github.com/Rainexn0b/keyRGB/issues/new/choose

Select **Hardware support / diagnostics** and paste the JSON output from step 1.

3) Include details:

- Laptop model (e.g., XMG Core 15, Tuxedo InfinityBook)
- USB ID (run `lsusb | grep -i "048d:"`)
- Description of what works vs. what fails

### Privacy note

`keyrgb-diagnostics` attempts to sanitize output, but please review the JSON before posting to ensure no personal paths/names are included.

## License

GPL-2.0-or-later.
