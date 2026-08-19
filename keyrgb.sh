#!/bin/bash
# KeyRGB launcher script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Use the project venv if present, fall back to system python3.
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# PyGObject is supplied by the distro and must match the interpreter's minor
# version. A uv-created venv can therefore have all Python dependencies while
# still missing `gi`; pystray then falls back to XEmbed/Xorg, which turns the
# transparent KeyRGB artwork into an opaque square on Plasma. When possible,
# borrow an installed/AppImage runtime for its desktop libraries. Keeping this
# checkout as cwd (and on PYTHONPATH for normal console-script runtimes) leaves
# the source tree authoritative.
if ! "$PYTHON" -c 'import gi; raise SystemExit(0 if callable(getattr(gi, "require_version", None)) else 1)' \
    >/dev/null 2>&1; then
    SOURCE_LAUNCHER="$(readlink -f "$0")"
    DESKTOP_RUNTIME=""
    OLD_IFS="$IFS"
    IFS=:
    for path_dir in $PATH; do
        [ -n "$path_dir" ] || path_dir="."
        candidate="$path_dir/keyrgb"
        [ -x "$candidate" ] || continue
        candidate_real="$(readlink -f "$candidate")"
        [ "$candidate_real" != "$SOURCE_LAUNCHER" ] || continue
        # An activated source-tree venv puts its generated console script first
        # on PATH, but that script uses the same GI-less interpreter we just
        # rejected. Keep searching for an independently installed runtime.
        case "$candidate_real" in
            "$SCRIPT_DIR"/.venv/*) continue ;;
        esac
        if [ -n "$candidate_real" ]; then
            DESKTOP_RUNTIME="$candidate"
            break
        fi
    done
    IFS="$OLD_IFS"

    if [ -n "$DESKTOP_RUNTIME" ]; then
        echo "KeyRGB: local Python lacks PyGObject; using installed desktop runtime for the tray icon." >&2
        export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
        exec "$DESKTOP_RUNTIME" "$@"
    fi
fi

# -B avoids stale __pycache__ bytecode issues when iterating in-place.
exec "$PYTHON" -B -m keyrgb.tray "$@"
