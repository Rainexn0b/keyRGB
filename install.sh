#!/bin/bash
# KeyRGB Installation Script

set -e

echo "=== KeyRGB Installation ==="
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Please run without sudo (script will ask for password when needed)"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check for USB device (048d:600b)
if ! lsusb | grep -q "048d:600b"; then
    echo "⚠️  Warning: ITE 8291 device (048d:600b) not found"
    echo "   Please make sure your keyboard is connected"
fi

# Install ite8291r3-ctl library
echo
echo "📦 Installing ite8291r3-ctl library..."
if [ ! -d "ite8291r3-ctl" ]; then
    echo "❌ ite8291r3-ctl directory not found"
    echo "   Please make sure the repository is cloned properly"
    exit 1
fi

cd ite8291r3-ctl
python3 -m pip install --user .
cd ..

echo "✓ ite8291r3-ctl installed"

# Install Python dependencies
echo
echo "📦 Installing Python dependencies..."
python3 -m pip install --user -r requirements.txt
echo "✓ Dependencies installed"

# Install KeyRGB itself (provides the `keyrgb` console script)
echo
echo "📦 Installing KeyRGB..."
python3 -m pip install --user -e .
echo "✓ KeyRGB installed"

# Create udev rule for non-root access
echo
echo "🔐 Setting up udev rules for USB access..."
UDEV_RULE='SUBSYSTEM=="usb", ATTR{idVendor}=="048d", ATTR{idProduct}=="600b", TAG+="uaccess"'
echo "$UDEV_RULE" | sudo tee /etc/udev/rules.d/99-ite8291-wootbook.rules > /dev/null

sudo udevadm control --reload
sudo udevadm trigger

echo "✓ Udev rules installed"
echo "  Note: If access still fails, log out/in or reboot so uaccess applies."

# Make scripts executable
echo
echo "🔧 Making scripts executable..."
chmod +x keyrgb

# Optional / legacy scripts (don't fail if absent)
for f in keyrgb-tray.py keyrgb-editor.py keyrgb-editor-qt.py effects.py; do
    if [ -f "$f" ]; then
        chmod +x "$f"
    fi
done

echo "✓ Scripts are executable"

# Create autostart entry
echo
echo "🚀 Setting up autostart..."
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/keyrgb.desktop"

KEYRGB_EXEC="$(command -v keyrgb || true)"
if [ -z "$KEYRGB_EXEC" ]; then
    # Fallback: run from repo location (works as long as the folder isn't moved)
    KEYRGB_EXEC="$PWD/keyrgb"
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
echo "  1. Run './keyrgb' to start the tray app"
echo "  2. Look for the pink/magenta keyboard icon in your system tray"
echo "  3. Right-click the icon to access effects, speed, and brightness"
echo "  4. KeyRGB will auto-start on next login"
echo
echo "Troubleshooting:"
echo "  - If icon doesn't appear, check terminal for errors"
echo "  - If keyboard doesn't light up, check USB device: lsusb | grep 048d"
echo "  - Per-key editor: Right-click tray icon → Per-Key Editor"
echo
