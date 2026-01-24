# KeyRGB

KeyRGB is a lightweight Linux tray app and per-key editor for laptop keyboard lighting. It serves as a practical, focused alternative to OpenRGB for supported devices.

> LLM note: For a concise, LLM-optimized summary of supported hardware, backends, and repo-discovery hints, see `AGENTS.md`.

## Supported Backends & Devices

KeyRGB uses a priority-based system to select the best driver for your hardware:

1.  **Kernel Driver (Preferred)**: Uses safe, native Linux kernel interfaces (`/sys/class/leds`).
    *   **Clevo / Tuxedo**: Full RGB support via `tuxedo-drivers` or `clevo-xsm-wmi`.
    *   **System76**: Full RGB support via standard ACPI drivers.
    *   **Universal**: Brightness control for almost any laptop (Dell, ASUS, HP, etc.).

2.  **USB Direct (Fallback)**: Uses the `ite8291r3` userspace driver.
    *   **TongFang**: Supports per-key RGB on devices without kernel drivers (XMG, Wootbook, Eluktronics, older Tuxedo models).

*The installer (`install.sh`) can optionally help you install the necessary kernel modules for Clevo/Tuxedo laptops.*

## Status

- **Beta**: versioning follows **0.x.y**.
- Developed primarily on Fedora / Nobara.
- Installer support is **best-effort** on other distros via common package managers (dnf/apt/pacman/zypper/apk).
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

<details>
<summary><b>More screenshots</b></summary>

<table>
	<tr>
		<td width="50%">
			<b>Tray Menu (Software Effects)</b><br>
			<img src="assets/screenshots/trayeffectssw.png" alt="Tray menu software effects">
		</td>
		<td width="50%">
			<b>Tray Menu (Keyboard / Profiles)</b><br>
			<img src="assets/screenshots/traykbp.png" alt="Tray menu keyboard and profiles">
		</td>
	</tr>
	<tr>
		<td width="50%">
			<b>Uniform Color UI</b><br>
			<img src="assets/screenshots/uniformcolorux.png" alt="Uniform color UI">
		</td>
		<td width="50%">
			<b>Per-Key Calibrator</b><br>
			<img src="assets/screenshots/perkeycalux.png" alt="Per-key calibrator">
		</td>
	</tr>
	<tr>
		<td width="50%">
			<b>Keymap Calibration</b><br>
			<img src="assets/screenshots/keymapcalux.png" alt="Keymap calibration">
		</td>
		<td width="50%">
			<b>Reactive Typing</b><br>
			<img src="assets/screenshots/reactivekb.png" alt="Reactive typing">
		</td>
	</tr>
</table>

</details>

## Quickstart

### Install

#### Standalone AppImage (recommended for most users)

Downloads the self-contained AppImage + sets up device permissions (udev rules + polkit helper). No system dependencies required.

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && bash install.sh --no-system-deps
```

The AppImage bundles all dependencies (Python, tkinter, libappindicator, libraries) for maximum portability. Works out-of-the-box on any distro.

#### Update existing AppImage (non-interactive)

Replaces `~/.local/bin/keyrgb` with the newest matching release. Reuses your last saved release channel (stable vs prerelease).

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && bash install.sh --update-appimage
```

#### Development install (local checkout)

For development or local modifications. Clones the repository, installs system dependencies (Python 3.12+, pip, build tools, libgirepository dev headers, python3-tk, libappindicator), creates a virtual environment, and installs keyrgb in editable mode.

```bash
./install_dev.sh
```

Or if you already cloned the repo:

```bash
./install.sh
```

Notes:

- Fedora / Nobara is the primary supported target.
- Other distros are best-effort via common package managers (dnf/apt/pacman/zypper/apk).
- System dependencies are only needed for development installs; the AppImage bundles everything.

Docs:

- Quickstart & install instructions: see the **Quickstart** section above.
- Commands / entrypoints / environment variables: see **Run** and **Environment variables** sections above.
- Architecture / TongFang support roadmap: [docs/architecture/tongfang/00-index.md](docs/architecture/tongfang/00-index.md)

### Uninstall

#### One-line uninstall (no clone)

Downloads and runs the latest uninstaller script:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/uninstall.sh -o uninstall.sh && bash uninstall.sh
```

#### Uninstall from a local checkout

```bash
# Interactive removal
./uninstall.sh

# Non-interactive (scripted)
./uninstall.sh --yes --remove-appimage
```

### Run

If you installed via the installer, run KeyRGB from your app menu or start it from a terminal:

| Command | Description |
| --- | --- |
| `keyrgb` | Start the tray app (background). |
| `./keyrgb` | Run attached to terminal (dev mode). |
| `keyrgb-perkey` | Open the per-key editor. |
| `keyrgb-uniform` | Open the uniform-color GUI. |
| `keyrgb-reactive-color` | Open the reactive typing color GUI. |
| `keyrgb-calibrate` | Open the keymap calibrator UI. |
| `keyrgb-settings` | Open the settings GUI. |
| `keyrgb-tcc-profiles` | Open the TCC power profiles GUI (if `tccd` is available). |
| `keyrgb-diagnostics` | Print hardware diagnostics JSON. |

### Environment variables

| Variable | Usage |
| --- | --- |
| `KEYRGB_BACKEND` | Force backend: `auto` (default), `ite8291r3`, or `sysfs-leds`. |
| `KEYRGB_DEBUG=1` | Enable verbose debug logging. |
| `KEYRGB_TK_SCALING` | Float override for UI scaling (High-DPI / fractional scaling). |
| `KEYRGB_TCCD_BIN` | Override the `tccd` helper path for TCC integration. |
| `KEYRGB_DEBUG_BRIGHTNESS` | When set to `1`, emits detailed logs for brightness actions and sysfs writes (useful when investigating flashes when restoring from dim). Example: `KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb dev state` |

### Tray effects (names)

These are the effect names stored in `~/.config/keyrgb/config.json` under the `effect` key.

- Hardware (firmware) effects: `rainbow`, `breathing`, `wave`, `ripple`, `marquee`, `raindrop`, `aurora`, `fireworks`
- Software effects: `rainbow_wave`, `rainbow_swirl`, `spectrum_cycle`, `color_cycle`, `chase`, `twinkle`, `strobe`
- Reactive typing: `reactive_fade`, `reactive_ripple`
- Per-key static map: `perkey`

## Configuration

### Settings and autostart

Access **Settings** via the tray menu to configure:

- **Power Management**: toggle LEDs on Suspend/Resume or Lid Close/Open.
- **Screen Dim Sync**: optionally sync keyboard brightness with desktop-driven screen dimming/brightness changes (e.g. KDE brightness slider).
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
| `--dev` | Developer install (editable pip install mode). |
| `--pip` | Legacy alias for dev editable install. |
| `--clone` | Clone repo and install via editable pip (dev/source). |
| `--clone-dir <path>` | Clone target directory (dev mode). |
| `--version <tag>` | Install specific tag (e.g. `v0.9.3`). |
| `--asset <name>` | Override AppImage filename (default: `keyrgb-x86_64.AppImage`). |
| `--prerelease` | Allow picking prereleases when auto-resolving latest AppImage. |
| `--no-system-deps` | Skip best-effort system dependency installation. |
| `--update-appimage` | Non-interactive: update an existing AppImage install (downloads latest and replaces `~/.local/bin/keyrgb`). |
| `--ref <git-ref>` | For curl installs: download installer modules from a specific git ref (default: `main`). |

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
