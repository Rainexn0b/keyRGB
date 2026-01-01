#!/bin/bash
# KeyRGB Installation Script

set -e

usage() {
        cat <<'EOF'
Usage:
    ./install.sh [--appimage] [--pip] [--version <tag>] [--asset <name>]

Modes:
    --appimage  Install by downloading the AppImage. (default)
    --pip       Install from this repo via pip (-e). (dev / editable install)

What gets installed (both modes):
    - System dependencies (best-effort via dnf when available)
    - Desktop launcher: ~/.local/share/applications/keyrgb.desktop
    - Autostart entry:  ~/.config/autostart/keyrgb.desktop
    - Icon:            ~/.local/share/icons/hicolor/256x256/apps/keyrgb.png
    - udev rule:       /etc/udev/rules.d/99-ite8291-wootbook.rules (requires sudo)

Mode details:
    --appimage
        - Downloads a single AppImage to: ~/.local/bin/keyrgb
        - Does NOT install Python packages via pip
    --pip
        - Installs Python packages into your user site-packages (pip --user)
        - Intended for development / editable installs

AppImage options:
    --version <tag>  Git tag to download from (e.g. v0.6.0). If omitted, uses GitHub "latest".
    --asset <name>   AppImage asset filename (default: keyrgb-x86_64.AppImage).

Env vars:
    KEYRGB_INSTALL_TUXEDO=y|n  Non-interactive default for optional TCC integration.
EOF
}

MODE=""
KEYRGB_VERSION="${KEYRGB_VERSION:-}"
KEYRGB_APPIMAGE_ASSET="${KEYRGB_APPIMAGE_ASSET:-keyrgb-x86_64.AppImage}"

while [ "$#" -gt 0 ]; do
        case "$1" in
                --pip|--repo)
                        MODE="pip"
                        shift
                        ;;
                --appimage)
                        MODE="appimage"
                        shift
                        ;;
                --version)
                        KEYRGB_VERSION="${2:-}"
                        shift 2
                        ;;
                --asset)
                        KEYRGB_APPIMAGE_ASSET="${2:-}"
                        shift 2
                        ;;
                -h|--help)
                        usage
                        exit 0
                        ;;
                *)
                        echo "Unknown argument: $1" >&2
                        usage
                        exit 2
                        ;;
        esac
done

# Always run relative to the repo root (where this script lives), even if invoked
# from another working directory.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=== KeyRGB Installation ==="
echo

if [ -z "$MODE" ]; then
    MODE="appimage"
fi

echo "Install mode: $MODE"

if [ "$MODE" = "appimage" ]; then
    echo "AppImage install target: $HOME/.local/bin/keyrgb"
else
    echo "Pip install target: user site-packages (pip --user)"
fi

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
    local pkgs=(
        python3
        python3-tkinter
        usbutils
        dbus-tools
        libappindicator-gtk3
        python3-gobject
        gtk3
    )

    # Only needed for repo/pip installs.
    if [ "$MODE" = "pip" ]; then
        pkgs+=(git python3-pip)
    fi

    sudo dnf install -y "${pkgs[@]}"

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

if [ "$MODE" = "pip" ]; then
    # Repo/pip install requires Python.
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required but not installed"
        exit 1
    fi
    echo "✓ Python 3 found: $(python3 --version)"
else
    # AppImage install can use curl/wget (preferred) or python3 as a fallback.
    if command -v curl &> /dev/null; then
        echo "✓ Downloader found: curl"
    elif command -v wget &> /dev/null; then
        echo "✓ Downloader found: wget"
    elif command -v python3 &> /dev/null; then
        echo "✓ Downloader found: python3 ($(python3 --version))"
    else
        echo "❌ Need one of: curl, wget, or python3 (to download the AppImage)" >&2
        exit 1
    fi
fi

# Check for git (needed to fetch upstream ite8291r3-ctl)
if [ "$MODE" = "pip" ]; then
    if ! command -v git &> /dev/null; then
        echo "❌ git is required but not installed"
        exit 1
    fi
fi

if [ "$MODE" = "pip" ]; then
    # Ensure pip is usable
    if ! python3 -m pip --version &> /dev/null; then
        echo "❌ python3-pip is required but pip is not available"
        exit 1
    fi

    echo
    echo "📦 Updating Python packaging tools..."
    python3 -m pip install --user -U pip setuptools wheel
    echo "✓ pip/setuptools/wheel updated"
fi

# Check for USB device (048d:600b)
if command -v lsusb &> /dev/null; then
    if ! lsusb | grep -q "048d:600b"; then
        echo "⚠️  Warning: ITE 8291 device (048d:600b) not found"
        echo "   Please make sure your keyboard is connected"
    fi
else
    echo "⚠️  lsusb not found; skipping USB device detection check."
fi

download_url() {
    local url="$1"
    local dst="$2"

    mkdir -p "$(dirname "$dst")"

    if command -v curl &> /dev/null; then
        curl -L --fail --silent --show-error -o "$dst" "$url"
        return 0
    fi

    if command -v wget &> /dev/null; then
        wget -q -O "$dst" "$url"
        return 0
    fi

    if command -v python3 &> /dev/null; then
        python3 - "$url" "$dst" <<'PY'
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

url = sys.argv[1]
dst = Path(sys.argv[2])
dst.parent.mkdir(parents=True, exist_ok=True)

with urllib.request.urlopen(url) as resp, dst.open("wb") as f:
    shutil.copyfileobj(resp, f)
PY
        return 0
    fi

    echo "❌ No downloader available (need curl, wget, or python3)" >&2
    return 1
}

install_appimage() {
    echo
    echo "📦 Installing KeyRGB AppImage..."

    local user_bin="$HOME/.local/bin"
    local app_dst="$user_bin/keyrgb"

    mkdir -p "$user_bin"

    local base
    if [ -n "$KEYRGB_VERSION" ]; then
        base="https://github.com/Rainexn0b/keyRGB/releases/download/$KEYRGB_VERSION"
        echo "✓ Using release tag: $KEYRGB_VERSION"
    else
        base="https://github.com/Rainexn0b/keyRGB/releases/latest/download"
        echo "✓ Using GitHub latest release"
    fi

    local url="$base/$KEYRGB_APPIMAGE_ASSET"
    echo "⬇️  Downloading: $url"
    download_url "$url" "$app_dst"
    chmod +x "$app_dst"
    echo "✓ Installed AppImage: $app_dst"
}

install_icon_and_desktop_entries() {
    local icon_dir="$HOME/.local/share/icons/hicolor/256x256/apps"
    local icon_file="$icon_dir/keyrgb.png"
    local app_dir="$HOME/.local/share/applications"
    local app_file="$app_dir/keyrgb.desktop"
    local autostart_dir="$HOME/.config/autostart"
    local autostart_file="$autostart_dir/keyrgb.desktop"
    local icon_ref="keyrgb"

    mkdir -p "$icon_dir" "$app_dir" "$autostart_dir"

    if [ "$MODE" = "pip" ]; then
        local icon_src="$REPO_DIR/assets/logo-keyrgb.png"
        if ! [ -f "$icon_src" ]; then
            echo "❌ Logo not found: $icon_src" >&2
            exit 1
        fi
        install -m 0644 "$icon_src" "$icon_file"
    else
        local raw_ref="main"
        if [ -n "$KEYRGB_VERSION" ]; then
            raw_ref="$KEYRGB_VERSION"
        fi
        local icon_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/assets/logo-keyrgb.png"
        echo "⬇️  Downloading icon: $icon_url"
        download_url "$icon_url" "$icon_file"
    fi

    echo "✓ Installed icon: $icon_file"

    cat > "$app_file" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=keyrgb
Icon=$icon_ref
Terminal=false
Categories=Utility;System;
StartupNotify=false
EOF

    echo "✓ App launcher installed (KeyRGB will appear in your app menu)"

    local keyrgb_exec
    keyrgb_exec="$(command -v keyrgb || true)"
    if [ -z "$keyrgb_exec" ]; then
        # Fallback: when PATH doesn't include ~/.local/bin yet.
        keyrgb_exec="$HOME/.local/bin/keyrgb"
    fi

    cat > "$autostart_file" << EOF
[Desktop Entry]
Type=Application
Name=KeyRGB
Comment=RGB Keyboard Controller
Exec=$keyrgb_exec
Icon=$icon_ref
Terminal=false
Categories=Utility;System;
X-KDE-autostart-after=plasma-workspace
X-KDE-StartupNotify=false
EOF

    echo "✓ Autostart configured"
}

install_udev_rule() {
    local src_rule
    local dst_rule="/etc/udev/rules.d/99-ite8291-wootbook.rules"
    local tmp_rule=""

    if [ "$MODE" = "pip" ]; then
        src_rule="$REPO_DIR/udev/99-ite8291-wootbook.rules"
        if ! [ -f "$src_rule" ]; then
            echo "⚠️  udev rule file not found: $src_rule"
            return 0
        fi
    else
        local raw_ref="main"
        if [ -n "$KEYRGB_VERSION" ]; then
            raw_ref="$KEYRGB_VERSION"
        fi
        local rule_url="https://raw.githubusercontent.com/Rainexn0b/keyRGB/$raw_ref/udev/99-ite8291-wootbook.rules"
        tmp_rule="$(mktemp)"
        echo "⬇️  Downloading udev rule: $rule_url"
        download_url "$rule_url" "$tmp_rule"
        src_rule="$tmp_rule"
    fi

    if ! command -v udevadm &> /dev/null; then
        echo "⚠️  udevadm not found; cannot install udev rule automatically."
        echo "   To fix permissions manually, copy a 99-ite8291-wootbook.rules into: $dst_rule"
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

    if [ -n "$tmp_rule" ]; then
        rm -f "$tmp_rule" 2>/dev/null || true
    fi
}

if [ "$MODE" = "pip" ]; then
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
else
    install_appimage
fi
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

if [ "$MODE" = "pip" ]; then
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
fi

echo
echo "🧷 Installing application launcher entry..."
install_icon_and_desktop_entries

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
