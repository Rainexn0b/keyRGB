
# Usage (Fedora)

This document describes how to install and run KeyRGB **from a blank Fedora install**.

KeyRGB is a Python tray app + GUIs (Tkinter) for ITE 8291 / ITE8291R3 laptop keyboards (typical USB ID: `048d:600b`).

## 0) Assumptions

- You are on Fedora Workstation (GNOME or KDE) or a desktop with an X11 or later tray.
- You have an ITE 8291 compatible keyboard connected (or you just want the app to start even if it is absent).
- You are installing from this repo checkout.

## 1) System dependencies (dnf)

If you're on Fedora (including Nobara) and you just want it working quickly, you can skip this entire manual section and run:

```bash
./install.sh
```

`install.sh` installs the needed Fedora packages (Python, pip, Tkinter, tray deps, etc.) via `dnf` and then installs the Python packages.

Use the steps below only if you prefer to install dependencies manually.

Update the OS first:

```bash
sudo dnf -y upgrade
sudo reboot
```

Install base tools:

```bash
sudo dnf install -y git python3 python3-pip
```

Install Tkinter (KeyRGB GUIs use Tk):

```bash
sudo dnf install -y python3-tkinter
```

Install tray/indicator support (pystray backend).

On Fedora **KDE Plasma**, tray icons typically work out of the box.

On Fedora **GNOME**, you typically want AppIndicator support:

```bash
sudo dnf install -y libappindicator-gtk3 python3-gobject gtk3
```

If your desktop does not show tray icons by default (GNOME), install and enable the AppIndicator extension:

```bash
sudo dnf install -y gnome-shell-extension-appindicator
```

Then log out/in (or reboot) so the extension is active.

## 2) Get the code

```bash
cd ~
git clone https://github.com/Rainexn0b/keyRGB.git keyrgb
cd keyrgb
```

KeyRGB depends on the `ite8291r3-ctl` userspace driver library.

## 3) Python install order (recommended: user install)

The simplest install path is:

```bash
./install.sh
```

That script:

- Installs Fedora system dependencies (via `dnf`)
- Installs upstream `ite8291r3-ctl` (and applies the one-line Wootbook `0x600B` patch if upstream hasn't merged it yet)
- Installs KeyRGB's Python dependencies
- Installs KeyRGB itself
- Sets up the udev rule for non-root USB access

If you prefer to do it manually (useful for development), follow the steps below.

Upgrade pip tooling:

```bash
python3 -m pip install --user -U pip setuptools wheel
```

Install the ITE control library first (upstream + the one-line Wootbook USB ID patch):

```bash
tmpdir="$(mktemp -d)"
git clone --depth 1 https://github.com/pobrn/ite8291r3-ctl.git "$tmpdir/ite8291r3-ctl"

# Add Wootbook's USB product id (0x600B) if upstream hasn't merged it yet.
python3 - "$tmpdir/ite8291r3-ctl/ite8291r3_ctl/ite8291r3.py" << 'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
lines = text.splitlines(True)
out = []
patched = False
for line in lines:
	if line.lstrip().startswith("PRODUCT_IDS") and "[" in line and "]" in line:
		if "0x600B" in line or "0x600b" in line:
			out.append(line)
			patched = True
			continue
		before, after = line.split("]", 1)
		if not before.rstrip().endswith(","):
			before = before.rstrip() + ","
		out.append(f"{before} 0x600B]{after}")
		patched = True
		continue
	out.append(line)
if not patched:
	raise SystemExit("Failed to patch PRODUCT_IDS")
path.write_text("".join(out), encoding="utf-8")
PY

python3 -m pip install --user "$tmpdir/ite8291r3-ctl"
rm -rf "$tmpdir"
```

Install KeyRGB’s Python dependencies:

```bash
python3 -m pip install --user -r requirements.txt
```

Install KeyRGB itself (editable mode, good for running from the repo):

```bash
python3 -m pip install --user -e .
```

At this point you should have the entrypoints:

- `keyrgb` (tray)
- `keyrgb-perkey` (per-key editor)
- `keyrgb-uniform` (uniform-color GUI)
- `keyrgb-calibrate` (keymap calibrator)

## 4) USB permissions (udev rule)

To control the keyboard without running as root, install the udev rule.

This repo’s installer uses:

```text
SUBSYSTEM=="usb", ATTR{idVendor}=="048d", ATTR{idProduct}=="600b", TAG+="uaccess"
```

You can either run the repo installer:

```bash
./install.sh
```

Or install just the udev rule manually:

```bash
sudo install -D -m 0644 packaging/udev/99-ite8291-wootbook.rules \
	/etc/udev/rules.d/99-ite8291-wootbook.rules

sudo udevadm control --reload
sudo udevadm trigger
```

Then **replug the keyboard** (if external) or **log out/in** (or reboot) so `uaccess` applies.

## 5) Run

From the repo:

```bash
./keyrgb
```

Or if installed:

```bash
keyrgb
```

If you don’t see the tray icon, launch from a terminal to see logs:

```bash
KEYRGB_DEBUG=1 keyrgb
```

## 6) Per-key setup (first-time calibration)

Per-key control requires a keymap calibration for your laptop model/revision.

1. Run the per-key editor: `keyrgb-perkey`
2. Click **Run Keymap Calibrator**
3. Follow the prompts until the mapping is complete
4. Save the profile

Profiles are stored under:

```text
~/.config/keyrgb/profiles/
```

## 7) Optional: TUXEDO Control Center (TCC) power profiles integration

If the TCC daemon (`tccd`) is installed and running, KeyRGB will show a **Power Profiles (TCC)** submenu in the tray and a GUI window for:

- Listing profiles
- Temporarily activating a profile (same behavior as the TCC tray)
- Creating/duplicating/renaming/deleting custom profiles
- Editing profile JSON (advanced)

Notes:

- Listing and temporary activation use **system DBus**.
- Creating/editing/deleting profiles requires admin permissions because it updates `/etc/tcc/profiles` via the `tccd` helper.
	- KeyRGB will try `pkexec` first (graphical prompt), then `sudo`.
- If your `tccd` helper binary is not at the default path, set it:

```bash
export KEYRGB_TCCD_BIN=/path/to/tccd
keyrgb
```

## 8) Troubleshooting

### Tray icon does not appear

- Confirm your desktop supports tray icons.
	- GNOME: install/enable `gnome-shell-extension-appindicator`.
- Run with debug logging: `KEYRGB_DEBUG=1 keyrgb`

Diagnostics (for bug reports):

```bash
keyrgb-diagnostics
```

### “Permission denied” / cannot open the USB device

- Ensure the udev rule exists: `/etc/udev/rules.d/99-ite8291-wootbook.rules`
- Reload + trigger udev, then log out/in or reboot.
- Verify the device is present:

```bash
lsusb | grep -i "048d:600b" || true
```

### Keyboard not detected

KeyRGB should still start, but it will show a warning in the tray menu and will not be able to apply effects.

### Power Profiles GUI says TCC is unavailable

- Confirm the daemon is present and running.
- Confirm DBus service is reachable.
- If edits fail, ensure `pkexec` is installed (package: `polkit`) or use `sudo`.

### Battery saver (optional)

KeyRGB can optionally dim keyboard brightness when you unplug AC power.

- Enable it in `~/.config/keyrgb/config.json`: set `battery_saver_enabled` to `true`.
- Set `battery_saver_brightness` to the desired brightness value.

