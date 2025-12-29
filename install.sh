#!/bin/bash
# KeyRGB Installation Script

set -e

# Always run relative to the repo root (where this script lives), even if invoked
# from another working directory.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=== KeyRGB Installation ==="
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run without sudo (script will ask for password when needed)"
    exit 1
fi

INSTALL_TUXEDO="n"

ask_yes_no() {
    local prompt="$1"
    local default="$2"  # y|n

    # Allow CI/non-interactive override.
    if [ -n "${KEYRGB_INSTALL_TUXEDO:-}" ]; then
        case "${KEYRGB_INSTALL_TUXEDO,,}" in
            y|yes|1|true) echo "y"; return 0 ;;
            n|no|0|false) echo "n"; return 0 ;;
        esac
    fi

    # Non-interactive: pick the default.
    if ! [ -t 0 ]; then
        echo "$default"
        return 0
    fi

    local suffix="[y/N]"
    if [ "$default" = "y" ]; then
        suffix="[Y/n]"
    fi

    local reply
    read -r -p "$prompt $suffix " reply || reply=""
    reply="${reply,,}"
    if [ -z "$reply" ]; then
        echo "$default"
        return 0
    fi

    case "$reply" in
        y|yes) echo "y" ;;
        n|no) echo "n" ;;
        *) echo "$default" ;;
    esac
}

echo
echo "Optional components:"
echo "  - Tuxedo Control Center (TCC) integration: shows 'Power Profiles' if TCC is installed."
INSTALL_TUXEDO="$(ask_yes_no "Enable optional TCC integration dependencies?" "n")"
if [ "$INSTALL_TUXEDO" = "y" ]; then
    echo "✓ TCC integration deps will be installed (best-effort)"
else
    echo "✓ Skipping TCC integration deps"
fi

install_system_deps_fedora() {
    echo
    echo "🔧 Installing system dependencies (Fedora / dnf)..."
    echo "   (This may prompt for your sudo password.)"

    # Minimal runtime deps:
    # - python3/pip: run KeyRGB
    # - python3-tkinter: GUI windows
    # - usbutils: lsusb (device check)
    # - dbus-tools: dbus-monitor used by power monitoring
    # - libappindicator-gtk3 + python3-gobject + gtk3: tray icon backends for pystray on Fedora
    # - polkit: pkexec for TCC profile writes (optional feature)
    sudo dnf install -y \
        git \
        python3 \
        python3-pip \
        python3-tkinter \
        usbutils \
        dbus-tools \
        libappindicator-gtk3 \
        python3-gobject \
        gtk3

    if [ "$INSTALL_TUXEDO" = "y" ]; then
        sudo dnf install -y polkit
    fi

    echo "✓ System dependencies installed"
    echo "  Note: KDE Plasma typically shows tray icons out of the box."
    echo "        GNOME may require the AppIndicator extension to show tray icons:"
    echo "        sudo dnf install -y gnome-shell-extension-appindicator"
    echo "        then log out/in (or reboot)."
}

# Best-effort system dependency installation.
if command -v dnf &> /dev/null; then
    install_system_deps_fedora
else
    echo "⚠️  dnf not found; skipping system package installation."
    echo "   You may need: python3, python3-pip, python3-tkinter, usbutils, dbus-tools, and tray deps for pystray."
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check for git (needed to fetch upstream ite8291r3-ctl)
if ! command -v git &> /dev/null; then
    echo "❌ git is required but not installed"
    exit 1
fi

# Ensure pip is usable
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ python3-pip is required but pip is not available"
    exit 1
fi

echo
echo "📦 Updating Python packaging tools..."
python3 -m pip install --user -U pip setuptools wheel
echo "✓ pip/setuptools/wheel updated"

# Check for USB device (048d:600b)
if command -v lsusb &> /dev/null; then
    if ! lsusb | grep -q "048d:600b"; then
        echo "⚠️  Warning: ITE 8291 device (048d:600b) not found"
        echo "   Please make sure your keyboard is connected"
    fi
else
    echo "⚠️  lsusb not found; skipping USB device detection check."
fi

# Install ite8291r3-ctl library (upstream + tiny local patch for Wootbook 0x600B)
echo
echo "📦 Installing ite8291r3-ctl library (upstream)..."

TMPDIR="$(mktemp -d)"
cleanup() {
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

git clone --depth 1 https://github.com/pobrn/ite8291r3-ctl.git "$TMPDIR/ite8291r3-ctl"

python3 - "$TMPDIR/ite8291r3-ctl/ite8291r3_ctl/ite8291r3.py" << 'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

if "0x600B" in text or "0x600b" in text:
    print("✓ ite8291r3-ctl already contains 0x600B")
    raise SystemExit(0)

# Fast path: exact upstream line.
text2 = text.replace(
    "PRODUCT_IDS = [0x6004, 0x6006, 0xCE00]",
    "PRODUCT_IDS = [0x6004, 0x6006, 0x600B, 0xCE00]  # Added 0x600B for Wootbook",
)

if text2 == text:
    # Generic path: patch PRODUCT_IDS assignment (single-line or multi-line).
    m = re.search(r"(?m)^PRODUCT_IDS\s*=\s*\[", text)
    if not m:
        raise SystemExit(f"Failed to locate PRODUCT_IDS in {path}")

    start = m.end()  # position right after '['
    end = text.find("]", start)
    if end == -1:
        raise SystemExit(f"Failed to find closing ']' for PRODUCT_IDS in {path}")

    body = text[start:end]
    if "0x600B" in body or "0x600b" in body:
        print("✓ ite8291r3-ctl already contains 0x600B")
        raise SystemExit(0)

    # If it's a single-line list, keep it single-line.
    if "\n" not in body:
        inner_stripped = body.strip()
        if inner_stripped and not inner_stripped.endswith(","):
            inner_stripped += ","
        new_body = f" {inner_stripped} 0x600B" + "  # Added 0x600B for Wootbook"
        text2 = text[:start] + new_body + text[end:]
    else:
        # Multi-line list: insert a new element before the closing bracket.
        last_nl = text.rfind("\n", 0, end)
        line_start = last_nl + 1 if last_nl != -1 else 0
        indent = re.match(r"\s*", text[line_start:end]).group(0)
        insertion = f"\n{indent}0x600B,  # Added 0x600B for Wootbook"
        text2 = text[:end] + insertion + text[end:]

path.write_text(text2, encoding="utf-8")
print("✓ Patched ite8291r3-ctl: added 0x600B to PRODUCT_IDS")
PY

python3 -m pip install --user "$TMPDIR/ite8291r3-ctl"

echo "✓ ite8291r3-ctl installed (upstream + local patch)"

# Install Python dependencies
echo
echo "📦 Installing Python dependencies..."
python3 -m pip install --user -r "$REPO_DIR/requirements.txt"
echo "✓ Dependencies installed"

# Install KeyRGB itself (provides the `keyrgb` console script)
echo
echo "📦 Installing KeyRGB..."
python3 -m pip install --user -e "$REPO_DIR"
echo "✓ KeyRGB installed"

install_udev_rule() {
    local src_rule="$REPO_DIR/packaging/udev/99-ite8291-wootbook.rules"
    local dst_rule="/etc/udev/rules.d/99-ite8291-wootbook.rules"

    if ! [ -f "$src_rule" ]; then
        echo "⚠️  udev rule file not found: $src_rule"
        return 0
    fi

    if ! command -v udevadm &> /dev/null; then
        echo "⚠️  udevadm not found; cannot install udev rule automatically."
        echo "   To fix permissions manually, copy: $src_rule -> $dst_rule"
        return 0
    fi

    echo
    echo "🔐 Installing udev rule for non-root USB access..."
    echo "   (This enables access to 048d:600b without running KeyRGB as root.)"
    echo "   (This may prompt for your sudo password.)"

    # Only overwrite if changed.
    if [ -f "$dst_rule" ] && cmp -s "$src_rule" "$dst_rule"; then
        echo "✓ udev rule already installed: $dst_rule"
    else
        sudo install -D -m 0644 "$src_rule" "$dst_rule"
        echo "✓ Installed udev rule: $dst_rule"
    fi

    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "✓ Reloaded udev rules"
    echo "  If KeyRGB is already running, quit and re-open it."
    echo "  If it still says permission denied, reboot once."
}

install_udev_rule

# Many distros don't include ~/.local/bin on PATH by default.
USER_BIN="$HOME/.local/bin"
if ! echo ":$PATH:" | grep -q ":$USER_BIN:"; then
    echo
    echo "⚠️  Your PATH does not include $USER_BIN"
    echo "   The 'keyrgb' command was installed there, so you may not be able to run it yet."
    echo
    echo "   To fix (bash/zsh), add this line to ~/.profile (or ~/.bashrc / ~/.zshrc):"
    echo "     export PATH=\"$USER_BIN:\$PATH\""
    echo
    echo "   Then restart your terminal (or log out/in)."
fi

# Make scripts executable
echo
echo "🔧 Making scripts executable..."
chmod +x "$REPO_DIR/keyrgb"

# Optional / legacy scripts (don't fail if absent)
for f in keyrgb-editor.py keyrgb-editor-qt.py effects.py; do
    if [ -f "$f" ]; then
        chmod +x "$f"
    fi
done

echo "✓ Scripts are executable"

# Create app launcher entry (so KeyRGB can be started again without a terminal)
echo
echo "🧷 Installing application launcher entry..."
APP_DIR="$HOME/.local/share/applications"
APP_FILE="$APP_DIR/keyrgb.desktop"

mkdir -p "$APP_DIR"

cat > "$APP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=keyrgb
Icon=preferences-desktop-keyboard
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF

echo "✓ App launcher installed (KeyRGB will appear in your app menu)"

# Create autostart entry
echo
echo "🚀 Setting up autostart..."
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/keyrgb.desktop"

KEYRGB_EXEC="$(command -v keyrgb || true)"
if [ -z "$KEYRGB_EXEC" ]; then
    # Fallback: run from repo location (works as long as the folder isn't moved)
    KEYRGB_EXEC="$REPO_DIR/keyrgb"
fi

mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_FILE" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$KEYRGB_EXEC
Icon=preferences-desktop-keyboard
Terminal=false
Categories=Utility;System;
X-KDE-autostart-after=plasma-workspace
X-KDE-StartupNotify=false
EOF

echo "✓ Autostart configured"

echo
echo "=== Installation Complete ==="
echo
echo "KeyRGB is now installed!"
echo
echo "Next steps:"
echo "  1. Run 'keyrgb' to start the tray app"
echo "     (Dev/repo mode: you can also run './keyrgb' from the repo folder.)"
echo "  2. Look for the pink/magenta keyboard icon in your system tray"
echo "  3. Right-click the icon to access effects, speed, and brightness"
echo "  4. KeyRGB will auto-start on next login"
echo "  5. If 'keyrgb' isn't found, ensure ~/.local/bin is on PATH"
echo "  6. If you quit the tray, you can re-open it from your app menu (KeyRGB)"
echo
echo "Troubleshooting:"
echo "  - If icon doesn't appear, check terminal for errors"
echo "  - If keyboard doesn't light up, check USB device: lsusb | grep 048d"
echo "  - Per-key editor: Right-click tray icon → Per-Key Editor"
echo
