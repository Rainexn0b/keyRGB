# KeyRGB

A lightweight Linux tray app and per-key editor for laptop keyboard lighting, with a focus on TongFang-based laptops using ITE controllers.

> LLM note: For a concise, LLM-optimized summary of supported hardware, backends, and repo-discovery hints, see `AGENTS.md`.

## Screenshots

| **Tray Menu (Effects)** | **Power Management** |
|---|---|
| ![Tray menu effects](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/trayeffects.png) | ![Tray power menu](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/traypp.png) |

| **Per-Key Editor** | **Settings** |
|---|---|
| ![Per-key editor](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/perkeyux.png) | ![Settings UI](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/settings.png) |

| **Tray Menu (Brightness)** | **RAM / CPU Usage** |
|---|---|
| ![Tray menu brightness](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/traybo.png) | ![RAM and CPU usage](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/ramusage.png) |

<details>
<summary><b>More screenshots</b></summary>

| **Tray Menu (Software Effects)** | **Tray Menu (Keyboard / Profiles)** |
|---|---|
| ![Tray menu software effects](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/trayeffectssw.png) | ![Tray menu keyboard and profiles](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/traykbp.png) |

| **Uniform Color UI** | **Per-Key Calibrator** |
|---|---|
| ![Uniform color UI](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/uniformcolorux.png) | ![Per-key calibrator](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/perkeycalux.png) |

| **Keymap Calibration** | **Reactive Typing** |
|---|---|
| ![Keymap calibration](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/keymapcalux.png) | ![Reactive typing](https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/assets/screenshots/reactivekb.png) |

</details>

## Quickstart

For most users, use the AppImage installer. Only use a source checkout if you want to modify KeyRGB locally.

### Install and update

#### Standalone AppImage (recommended)

The installer downloads the AppImage, stores it as `~/.local/bin/keyrgb.AppImage`, installs the `~/.local/bin/keyrgb` launcher, and refreshes desktop integration. The AppImage bundles the runtime dependencies, so normal installs do not need Python/Tk GUI packages from your distro.

Standard install:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && bash install.sh
```

AppImage install without system package changes:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && bash install.sh --no-system-deps
```

Update an existing AppImage install:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && bash install.sh --update-appimage
```

Notes:

- Some integration steps may prompt for `sudo` when installing udev or polkit rules.
- `--update-appimage` also refreshes desktop integration and removes stale legacy KeyRGB PNG icons from older installs when the current SVG icon is available.
- `--no-system-deps` only skips system package changes; it still downloads and installs the AppImage.
- On Arch/CachyOS, install `fuse2` for native AppImage/FUSE launching: `sudo pacman -S --needed fuse2`. KeyRGB also installs a launcher wrapper that falls back to `--appimage-extract-and-run` when `libfuse.so.2` is unavailable.
- On Debian/Ubuntu/Linux Mint, the AppImage path is usually enough for a first install. Optional kernel-driver installs are best-effort and may require TUXEDO package sources; KeyRGB does not add third-party apt repos automatically.
- To pin a release tag instead of `main`, use both `--ref <tag>` and `--version <tag>`.

### Uninstall

Interactive uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/uninstall.sh -o uninstall.sh && bash uninstall.sh
```

Non-interactive uninstall of the AppImage install and desktop entries:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/uninstall.sh -o uninstall.sh && bash uninstall.sh --yes --remove-appimage
```

<details>
<summary><b>Advanced usage and source checkout</b></summary>

#### Clone and install for local development

```bash
git clone https://github.com/Rainexn0b/keyRGB.git
cd keyRGB
./install.sh --dev
```

This installs system dependencies as needed and installs KeyRGB in editable mode. Fedora/Nobara and Arch/CachyOS are the main tested development targets; other distros are best-effort.

#### Uninstall from a local checkout

```bash
./uninstall.sh
./uninstall.sh --yes --remove-appimage
```

#### Installer arguments

| Argument | Meaning |
| --- | --- |
| `--appimage` | Download AppImage (default). |
| `--dev` | Developer install in editable mode. |
| `--pip` | Legacy alias for the editable developer install. |
| `--clone` | Clone repo and install from source. |
| `--clone-dir <path>` | Clone target directory. |
| `--version <tag>` | Install a specific tag such as `v0.17.2`. |
| `--asset <name>` | Override the AppImage filename. |
| `--prerelease` | Allow prereleases when resolving the latest AppImage. |
| `--no-system-deps` | Skip system package changes such as kernel-driver, TCC, or polkit installs. |
| `--update-appimage` | Refresh an existing AppImage install and desktop integration. |
| `--ref <git-ref>` | Download installer modules from a specific git ref. |

Full non-interactive install example:

```bash
curl -fsSL https://raw.githubusercontent.com/Rainexn0b/keyRGB/main/install.sh -o install.sh && \
	KEYRGB_INSTALL_KERNEL_DRIVERS=y \
	KEYRGB_INSTALL_INPUT_UDEV=y \
	KEYRGB_INSTALL_TUXEDO=y \
	KEYRGB_INSTALL_TCC_APP=y \
	bash install.sh
```

</details>

### Run

If you installed via the installer, run KeyRGB from your app menu or start it from a terminal:

| Command                 | Description                                               |
| ----------------------- | --------------------------------------------------------- |
| `keyrgb`                | Start the tray app (background).                          |
| `./keyrgb`              | Run attached to terminal (dev mode).                      |
| `keyrgb-perkey`         | Open the per-key editor.                                  |
| `keyrgb-uniform`        | Open the uniform-color GUI.                               |
| `keyrgb-reactive-color` | Open the reactive typing color GUI.                       |
| `keyrgb-calibrate`      | Open the keymap calibrator UI.                            |
| `keyrgb-settings`       | Open the settings GUI.                                    |
| `keyrgb-tcc-profiles`   | Open the TCC power profiles GUI (if `tccd` is available). |
| `keyrgb-diagnostics`    | Print hardware diagnostics JSON.                          |

### Environment variables

| Variable                                | Usage                                                                                                                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `KEYRGB_BACKEND`                        | Force backend: `auto` (default), `sysfs-leds`, `ite8291r3`, `ite8910`, `asusctl-aura`, or the experimental `ite8297` / `ite8233` / `ite8258` / `ite8291` / `ite8291-zones` / `ite8295-zones` backends when experimental backends are enabled. |
| `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1` | Opt in to experimental backends without using the Settings window.                                                                                                                                |
| `KEYRGB_ITE8295_ZONES_HIDRAW_PATH`      | Override the detected `/dev/hidraw*` node for the experimental `ite8295-zones` backend (mainly for diagnostics / testing).                                                                        |
| `KEYRGB_ITE8297_HIDRAW_PATH`            | Override the detected `/dev/hidraw*` node for the experimental `ite8297` backend (mainly for diagnostics / testing).                                                                              |
| `KEYRGB_ITE8233_HIDRAW_PATH`            | Override the detected `/dev/hidraw*` node for the experimental `ite8233` lightbar backend (mainly for diagnostics / testing).                                                                     |
| `KEYRGB_DEBUG=1`                        | Enable verbose debug logging.                                                                                                                                                                     |
| `KEYRGB_TK_SCALING`                     | Float override for UI scaling (High-DPI / fractional scaling).                                                                                                                                    |
| `KEYRGB_TCCD_BIN`                       | Override the `tccd` helper path for TCC integration.                                                                                                                                              |
| `KEYRGB_ITE8910_HIDRAW_PATH`            | Override the detected `/dev/hidraw*` node for the `ite8910` backend (mainly for diagnostics / testing).                                                                                           |
| `KEYRGB_DEBUG_BRIGHTNESS`               | When set to `1`, emits detailed logs for brightness actions and sysfs writes (useful when investigating flashes when restoring from dim). Example: `KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb dev state` |

### Tray effects (names)

These are the effect names stored in `~/.config/keyrgb/config.json` under the `effect` key.

- Hardware (firmware) effects: backend-specific. Common legacy values include `rainbow`, `breathing`, `wave`, `ripple`, `marquee`, `raindrop`, `aurora`, `fireworks`.
- Software effects: `rainbow_wave`, `rainbow_swirl`, `spectrum_cycle`, `color_cycle`, `chase`, `twinkle`, `strobe`
- Reactive typing: `reactive_fade`, `reactive_ripple`
- Per-key static map: `perkey`

When a hardware effect name collides with a software effect name, KeyRGB stores the hardware selection with an `hw:` prefix to preserve the user's choice. Example: hardware `spectrum_cycle` is stored as `hw:spectrum_cycle`.

## Status

- **Beta**: versioning follows **0.x.y**. Currently stable but has limited backend support.
- Installer support is validated on Fedora/Nobara and Arch/CachyOS; other distro families are supported on a staged, best-effort basis.
- Support depends entirely on your specific keyboard controller and firmware. See **Troubleshooting** and **Hardware support and contributing** below.

### Distro support profiles

| Profile                                | Status       | Notes                                                                                                                      |
| -------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Fedora / Red Hat family                | Tested       | Tested path. AppImage + optional `dnf`-based helpers is the smoothest path.                                                |
| Debian / Ubuntu / Linux Mint           | Experimental | AppImage-first is recommended. Optional apt kernel-driver installs are best-effort and may require TUXEDO package sources. |
| Arch / CachyOS / EndeavourOS / Manjaro | Tested       | Tested path. AppImage-first is recommended. KeyRGB does not install AUR DKMS packages automatically.                       |
| openSUSE / Other Linux                 | Best-effort  | AppImage-first is recommended. Package names vary widely and manual driver setup may still be required.                    |

## Supported Backends & Devices

Uses a priority-based backend system plus a backend-stability policy to select the most appropriate eligible backend for detected hardware.

1.  **Kernel Driver (Preferred)**: Uses safe, native Linux kernel interfaces (`/sys/class/leds`).
    *   **Clevo / Tuxedo**: Full RGB support via `tuxedo-drivers` or `clevo-xsm-wmi`.
    *   **System76**: Full RGB support via standard ACPI drivers.
	*   **Broad**: Brightness control on many laptops that expose a keyboard backlight LED via `/sys/class/leds`.

2.  **USB / HID Direct**: Uses an implemented userspace backend such as `ite8291r3` or `ite8910`.
    *   **TongFang**: Supports per-key RGB on devices without kernel drivers (XMG, Wootbook, Eluktronics, older Tuxedo models) if the hardware supports it.

3.  **ASUS Aura**: Uses the `asusctl-aura` backend when the ASUS userspace stack is available.
	*   **ASUS**: Best for laptops that already expose lighting control through `asusctl` / `rog-control-center`.

### Backend policy

| Stability      | Meaning                                                                                                                             |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `validated`    | Eligible by default during automatic backend selection.                                                                             |
| `experimental` | Shipped in-tree, but only considered after you opt in via **Settings → Backend policy** or `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1`. |
| `dormant`      | Present for research / future work, but never selected yet.                                                                         |

Experimental backends also carry an evidence tag in diagnostics so maintainers can distinguish speculative implementations from research-backed ones based on public protocol notes or reverse-engineering work.

Current backend plan:

- `sysfs-leds`, `ite8291r3`, `ite8910`, and `asusctl-aura`: `validated`
- `ite8297`: `experimental` + `reverse_engineered`
  - `0x048d:0x8297` — 64-byte hidraw feature-report path, uniform color only
- `ite8258`: `experimental` + `reverse_engineered`
	- `0x048d:0xc195` — Lenovo Legion 5 / Pro 5 Gen 10 24-zone ITE 8258 hidraw keyboard path (4×6 logical zone matrix, static color, brightness, and firmware effects)
- `ite8295-zones`: `experimental` + `reverse_engineered`
	- `0x048d:0xc963` — Lenovo 4-zone ITE 8295 hidraw keyboard path used by IdeaPad Gaming 3-class systems, with static color, 4-zone updates, brightness, and the confirmed default firmware effects (`breathing`, `wave`, `spectrum_cycle`)
	- `0x048d:0xc966` — companion ITE 8176 endpoint reported on the same laptops; still treated as a separate unsupported protocol family until direct RGB evidence exists
- `sysfs-mouse`: `experimental` + `speculative`
	- Auxiliary-only route for color-capable external mouse LEDs exposed through `/sys/class/leds`; surfaced through discovery and tray secondary-device contexts, but intentionally kept out of primary keyboard auto-selection
- `ite8233`: `experimental` + `reverse_engineered`
  - `0x048d:0x7001` — single-zone lightbar, static color / brightness / off
  - `0x048d:0x7000` — lightbar + hidden backend-level effects: `breathing`, `wave`, `bounce`/`clash`, `catchup`/`catch_up`
  - `0x048d:0x6010` — lightbar + hidden backend-level effects: `breathing`, `flash` (with optional direction), vendor DMI color-scaling quirk for specific SKUs
- `ite8291`: `experimental` + `reverse_engineered`
  - `0x048d:0x6004`, `0x6008`, `0x600b` — full per-key 6×21 row protocol
  - `0x048d:0xce00` (bcdDevice ≠ `0x0002`) — per-key path; `bcdDevice 0x0002` is routed to `ite8291-zones` instead
- `ite8291-zones`: `experimental` + `reverse_engineered`
  - `0x048d:0xce00` bcdDevice `0x0002` — 4-zone uniform-color firmware split

When a compatible auxiliary device is present, the tray exposes a `Software Targets` submenu so looped software effects can stay on the keyboard or mirror their uniformized output to all compatible secondary devices.

Note: direct ITE backends only enable known-good, whitelisted IDs. Experimental and dormant paths are additionally policy-gated, so detection alone does not guarantee automatic selection.

*The installer (`install.sh`) can optionally help you install the necessary kernel modules for Clevo/Tuxedo laptops, and installs the matching KeyRGB udev rules for supported USB / `hidraw` access paths.*

## Configuration

### Settings and autostart

Access **Settings** via the tray menu to configure:

- **Power Management**: toggle LEDs on Suspend/Resume or Lid Close/Open.
- **Screen Dim Sync**: optionally sync keyboard brightness with desktop-driven screen dimming/brightness changes (e.g. KDE brightness slider).
- **Autostart**: enable “Start KeyRGB on login”.
- **Backend policy**: opt in to experimental backends. Currently `ite8297`, `ite8233`, `ite8258`, `ite8291`, `ite8291-zones`, and `ite8295-zones` are experimental; the UI labels experimental paths as speculative or research-backed.

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

| Issue                                                                 | Solution                                                                                                                                                                                                                                                                                                                            |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| No tray icon                                                          | Run `keyrgb` from a terminal to see errors. Check if the system tray extension is enabled (GNOME).                                                                                                                                                                                                                                  |
| Permission denied                                                     | Ensure KeyRGB udev rules are installed. Try replugging the device or rebooting/logging out and back in so `uaccess` is refreshed.                                                                                                                                                                                                   |
| `0x048d:0x8910` is detected but not working                           | Ensure KeyRGB udev rules are installed and you have rebooted/logged out and back in. Run `keyrgb-diagnostics` to check backend selection.                                                                                                                                                                                           |
| Flickering effects                                                    | Ensure other tools (OpenRGB, TCC) are not running. KeyRGB needs exclusive access.                                                                                                                                                                                                                                                   |
| Per-key not working                                                   | You likely need to run the Keymap Calibrator first.                                                                                                                                                                                                                                                                                 |
| Brightness works but color does not (Kernel Driver / `kbd_backlight`) | Your sysfs LED node is likely **brightness-only** (no `multi_intensity`, `color`, or `rgb` attribute under `/sys/class/leds/*kbd_backlight*`). KeyRGB can only change color when the kernel exposes RGB attributes (common on Clevo/Tuxedo/System76). On ASUS ROG laptops, use `asusctl` / rog-control-center for Aura/RGB control. |
| Per-key editor not available on your laptop                           | The per-key editor requires a backend that can address individual LEDs (typically the USB ITE/TongFang path). Many kernel drivers expose only uniform brightness (and sometimes uniform RGB), not per-key RGB.                                                                                                                      |

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
