from __future__ import annotations

from pathlib import Path

import pytest

from tests.installer.hardware_access.test_hardware_access_unit import (
    _ENTRY,
    _INSTALL,
    _LIB,
    _REPO_ROOT,
    _run,
    _write_executable,
)


def test_download_failure_does_not_fall_back_to_main(tmp_path: Path) -> None:
    curl_log = tmp_path / "curl.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "curl",
        f"#!/bin/bash\nprintf '%s\\n' \"$*\" >> '{curl_log}'\nexit 22\n",
    )
    dest = tmp_path / "fetched"
    dest.mkdir()
    script = f"""
    set -euo pipefail
    source "{_LIB}"
    if hardware_access_fetch_payload "v9.9.9-missing" "{dest}" 0 0; then
      exit 0
    fi
    exit 12
    """
    completed = _run(script, env={"PATH": f"{bin_dir}:/usr/bin:/bin"})

    assert completed.returncode == 12, completed.stderr
    urls = curl_log.read_text(encoding="utf-8")
    assert "v9.9.9-missing" in urls
    assert "/main/" not in urls
    assert urls.count("https://") == 1
    assert not any(path.is_file() for path in dest.rglob("*"))


def test_dispatcher_routes_hardware_mode_without_user_install() -> None:
    help_run = _run(f"'{_INSTALL}' --hardware-access-only --help")
    assert help_run.returncode == 0, help_run.stderr
    assert "hardware-access" in help_run.stdout.lower() or "--reactive-input" in help_run.stdout
    assert "Downloading AppImage" not in help_run.stdout
    assert "Downloading AppImage" not in help_run.stderr

    unknown = _run(f"'{_INSTALL}' --hardware-access-only --not-a-real-flag")
    assert unknown.returncode == 12
    assert "unknown-argument" in unknown.stdout
    assert "Downloading AppImage" not in unknown.stderr

    combined = _run(f"'{_INSTALL}' --dev --hardware-access-only")
    assert combined.returncode == 1
    assert "cannot be combined" in combined.stderr


def test_bootstrap_fetches_hardware_scripts_but_not_system_payloads() -> None:
    text = _INSTALL.read_text(encoding="utf-8")
    assert "scripts/install_hardware_access.sh" in text
    assert "scripts/lib/hardware_access.sh" in text
    assert "scripts/lib/uninstall_match.sh" in text
    for line in text.splitlines():
        if "curl " in line and "system/" in line:
            raise AssertionError(f"bootstrap downloads a system payload: {line}")


def test_new_mode_does_not_source_installer_loader() -> None:
    for path in (_LIB, _ENTRY):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "common.sh" not in stripped
            assert "user_integration.sh" not in stripped
            assert "require_not_root" not in stripped
    assert "raw.githubusercontent.com" not in _ENTRY.read_text(encoding="utf-8")
    apply_body = _LIB.read_text(encoding="utf-8").split("hardware_access_apply()", 1)[1]
    assert "raw.githubusercontent.com" not in apply_body
    assert "curl " not in apply_body


def test_existing_helpers_delegate_file_placement_without_removing_fallbacks() -> None:
    user_integration = (_REPO_ROOT / "scripts" / "lib" / "user_integration.sh").read_text(encoding="utf-8")
    privileged = (_REPO_ROOT / "scripts" / "lib" / "privileged_helpers.sh").read_text(encoding="utf-8")
    install_user = (_REPO_ROOT / "scripts" / "install_user.sh").read_text(encoding="utf-8")

    assert "hardware_access_place_file_privileged" in user_integration
    assert "hardware_access_place_file_privileged" in privileged
    assert "install_udev_rule_from_ref" in install_user
    assert "trying main" in user_integration
    assert "reload_udev_rules_best_effort" in user_integration
    assert "/usr/local/bin/keyrgb-power-helper" in privileged


@pytest.mark.parametrize("forbidden", ["exit 126", "exit 127"])
def test_worker_does_not_use_pkexec_launch_statuses(forbidden: str) -> None:
    combined = _LIB.read_text(encoding="utf-8") + _ENTRY.read_text(encoding="utf-8")
    assert forbidden not in combined
