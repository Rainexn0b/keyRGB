from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MATCH_LIB = _REPO_ROOT / "scripts" / "lib" / "uninstall_match.sh"
_UDEV_DIR = _REPO_ROOT / "system" / "udev"


def _bash_eval(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=_REPO_ROOT,
    )


def test_current_repo_udev_rules_carry_stable_managed_markers() -> None:
    usb = (_UDEV_DIR / "99-ite8291-wootbook.rules").read_text(encoding="utf-8")
    sysfs = (_UDEV_DIR / "99-keyrgb-sysfs-leds.rules").read_text(encoding="utf-8")
    input_rule = (_UDEV_DIR / "99-keyrgb-input-uaccess.rules").read_text(encoding="utf-8")

    assert "KEYRGB_MANAGED_UDEV_RULE=usb-hidraw" in usb
    assert "KEYRGB_MANAGED_UDEV_RULE=sysfs-leds" in sysfs
    assert "KEYRGB_MANAGED_UDEV_RULE=input-uaccess" in input_rule


def test_uninstall_match_helpers_recognize_current_and_legacy_rules(tmp_path: Path) -> None:
    assert _MATCH_LIB.is_file()

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "current-usb.rules").write_text(
        (_UDEV_DIR / "99-ite8291-wootbook.rules").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (sandbox / "legacy-usb.rules").write_text(
        '# Allow user access to ITE 8291 USB device.\nSUBSYSTEM=="usb"\n',
        encoding="utf-8",
    )
    (sandbox / "legacy-header-usb.rules").write_text(
        '# Allow user access to supported ITE / Lenovo USB / hidraw devices.\nSUBSYSTEM=="usb"\n',
        encoding="utf-8",
    )
    (sandbox / "current-sysfs.rules").write_text(
        (_UDEV_DIR / "99-keyrgb-sysfs-leds.rules").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (sandbox / "current-input.rules").write_text(
        (_UDEV_DIR / "99-keyrgb-input-uaccess.rules").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (sandbox / "legacy-input-old-marker.rules").write_text(
        '# Reactive Typing effects need uaccess\nSUBSYSTEM=="input"\n',
        encoding="utf-8",
    )
    (sandbox / "foreign.rules").write_text(
        '# Vendor lighting ACL rules\nSUBSYSTEM=="usb"\n',
        encoding="utf-8",
    )

    script = textwrap.dedent(
        f"""
        set -euo pipefail
        source "{_MATCH_LIB}"
        sandbox="{sandbox}"

        is_keyrgb_managed_usb_udev_rule "$sandbox/current-usb.rules"
        is_keyrgb_managed_usb_udev_rule "$sandbox/legacy-usb.rules"
        is_keyrgb_managed_usb_udev_rule "$sandbox/legacy-header-usb.rules"
        is_keyrgb_managed_sysfs_udev_rule "$sandbox/current-sysfs.rules"
        is_keyrgb_managed_input_udev_rule "$sandbox/current-input.rules"
        is_keyrgb_managed_input_udev_rule "$sandbox/legacy-input-old-marker.rules"

        if is_keyrgb_managed_usb_udev_rule "$sandbox/foreign.rules"; then
          echo "foreign usb incorrectly managed" >&2
          exit 2
        fi
        if is_keyrgb_managed_sysfs_udev_rule "$sandbox/foreign.rules"; then
          echo "foreign sysfs incorrectly managed" >&2
          exit 3
        fi
        if is_keyrgb_managed_input_udev_rule "$sandbox/foreign.rules"; then
          echo "foreign input incorrectly managed" >&2
          exit 4
        fi

        # Bootstrap-style: no source tree available, marker alone is enough.
        should_remove_managed_file "$sandbox/current-usb.rules" "$sandbox/missing-src.rules" is_keyrgb_managed_usb_udev_rule
        should_remove_managed_file "$sandbox/current-input.rules" "$sandbox/missing-src.rules" is_keyrgb_managed_input_udev_rule

        # Exact source match still works without relying on markers.
        cp "$sandbox/current-usb.rules" "$sandbox/src-usb.rules"
        should_remove_managed_file "$sandbox/current-usb.rules" "$sandbox/src-usb.rules" is_keyrgb_managed_usb_udev_rule

        # Foreign rules are not removable even when a source path is missing.
        if should_remove_managed_file "$sandbox/foreign.rules" "$sandbox/missing-src.rules" is_keyrgb_managed_usb_udev_rule; then
          echo "foreign rule incorrectly removable" >&2
          exit 5
        fi

        echo ok
        """
    )

    completed = _bash_eval(script)
    assert completed.returncode == 0, completed.stdout
    assert "ok" in completed.stdout


def test_bootstrap_uninstall_dispatcher_fetches_match_helper() -> None:
    text = (_REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
    assert "scripts/lib/uninstall_match.sh" in text


def test_sandbox_uninstall_removes_managed_udev_without_repo_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end sandbox: bootstrap-like tree (scripts only) still removes managed rules."""

    staging = tmp_path / "keyrgb"
    scripts = staging / "scripts"
    scripts_lib = scripts / "lib"
    fake_etc = tmp_path / "etc" / "udev" / "rules.d"
    scripts_lib.mkdir(parents=True)
    fake_etc.mkdir(parents=True)

    shutil.copy2(_REPO_ROOT / "scripts" / "lib" / "uninstall_match.sh", scripts_lib / "uninstall_match.sh")

    # Minimal stubs for common.sh helpers used by the udev removal path.
    (scripts / "common.sh").write_text(
        textwrap.dedent(
            """
            #!/usr/bin/env bash
            log_info() { printf 'INFO %s\\n' "$*"; }
            log_ok() { printf 'OK %s\\n' "$*"; }
            log_warn() { printf 'WARN %s\\n' "$*"; }
            die() { printf 'DIE %s\\n' "$*" >&2; exit 1; }
            require_not_root() { :; }
            reload_udev_rules_best_effort() { :; }
            is_appimage_file() { return 1; }
            refresh_desktop_integration_caches_best_effort() { :; }
            pkg_remove_best_effort() { return 1; }
            """
        ).lstrip(),
        encoding="utf-8",
    )

    # Focused udev-only uninstall driver that reuses production match helpers.
    (scripts / "uninstall_udev_sandbox.sh").write_text(
        textwrap.dedent(
            """
            #!/usr/bin/env bash
            set -euo pipefail
            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/common.sh"
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/lib/uninstall_match.sh"

            UDEV_ROOT="${KEYRGB_TEST_UDEV_ROOT}"
            UDEV_DST="$UDEV_ROOT/99-ite8291-wootbook.rules"
            SYSFS_UDEV_DST="$UDEV_ROOT/99-keyrgb-sysfs-leds.rules"
            INPUT_UDEV_DST="$UDEV_ROOT/99-keyrgb-input-uaccess.rules"
            FOREIGN_DST="$UDEV_ROOT/99-foreign.rules"
            # Intentionally missing source tree (bootstrap style).
            UDEV_SRC="$SCRIPT_DIR/../system/udev/99-ite8291-wootbook.rules"
            SYSFS_UDEV_SRC="$SCRIPT_DIR/../system/udev/99-keyrgb-sysfs-leds.rules"
            INPUT_UDEV_SRC="$SCRIPT_DIR/../system/udev/99-keyrgb-input-uaccess.rules"

            remove_if_managed() {
              local dst="$1" src="$2" fn="$3"
              if should_remove_managed_file "$dst" "$src" "$fn"; then
                rm -f "$dst"
                log_ok "removed $(basename "$dst")"
              else
                log_warn "kept $(basename "$dst")"
              fi
            }

            remove_if_managed "$UDEV_DST" "$UDEV_SRC" is_keyrgb_managed_usb_udev_rule
            remove_if_managed "$SYSFS_UDEV_DST" "$SYSFS_UDEV_SRC" is_keyrgb_managed_sysfs_udev_rule
            remove_if_managed "$INPUT_UDEV_DST" "$INPUT_UDEV_SRC" is_keyrgb_managed_input_udev_rule
            remove_if_managed "$FOREIGN_DST" "$UDEV_SRC" is_keyrgb_managed_usb_udev_rule
            """
        ).lstrip(),
        encoding="utf-8",
    )
    os.chmod(scripts / "uninstall_udev_sandbox.sh", 0o755)

    shutil.copy2(_UDEV_DIR / "99-ite8291-wootbook.rules", fake_etc / "99-ite8291-wootbook.rules")
    shutil.copy2(_UDEV_DIR / "99-keyrgb-sysfs-leds.rules", fake_etc / "99-keyrgb-sysfs-leds.rules")
    shutil.copy2(_UDEV_DIR / "99-keyrgb-input-uaccess.rules", fake_etc / "99-keyrgb-input-uaccess.rules")
    (fake_etc / "99-foreign.rules").write_text("# other project\n", encoding="utf-8")

    completed = subprocess.run(
        ["bash", str(scripts / "uninstall_udev_sandbox.sh")],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "KEYRGB_TEST_UDEV_ROOT": str(fake_etc)},
    )
    assert completed.returncode == 0, completed.stdout
    assert not (fake_etc / "99-ite8291-wootbook.rules").exists()
    assert not (fake_etc / "99-keyrgb-sysfs-leds.rules").exists()
    assert not (fake_etc / "99-keyrgb-input-uaccess.rules").exists()
    assert (fake_etc / "99-foreign.rules").exists()
