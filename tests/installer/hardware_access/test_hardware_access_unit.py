from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIB = _REPO_ROOT / "scripts" / "lib" / "hardware_access.sh"
_ENTRY = _REPO_ROOT / "scripts" / "install_hardware_access.sh"
_INSTALL = _REPO_ROOT / "install.sh"
_SYSTEM = _REPO_ROOT / "system"
_USB_REL = "udev/99-ite8291-wootbook.rules"
_SYSFS_REL = "udev/99-keyrgb-sysfs-leds.rules"
_INPUT_REL = "udev/99-keyrgb-input-uaccess.rules"
_HELPER_REL = "bin/keyrgb-power-helper"
_POLKIT_RULE_REL = "polkit/90-keyrgb-power-helper.rules"
_POLKIT_ACTION_REL = "polkit/org.keyrgb.power-helper.policy"


def _run(
    script: str, *, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.pop("KEYRGB_INSTALL_POWER_HELPER", None)
    merged.pop("KEYRGB_INSTALL_INPUT_UDEV", None)
    if env:
        merged.update(env)
    return subprocess.run(
        ["/bin/bash", "-c", script],
        check=False,
        text=True,
        capture_output=True,
        cwd=cwd or _REPO_ROOT,
        env=merged,
    )


def _sha256(path: Path) -> str:
    completed = subprocess.run(
        ["sha256sum", "--", str(path)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return completed.stdout.split()[0]


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _link_tool(bin_dir: Path, name: str) -> None:
    source = shutil.which(name)
    if source is None:
        raise AssertionError(f"required host tool missing: {name}")
    (bin_dir / name).symlink_to(source)


def _tool_path(tmp_path: Path, *, udevadm: str | None, include_python: bool, install_text: str | None = None) -> Path:
    bin_dir = tmp_path / "bin"
    if bin_dir.exists():
        shutil.rmtree(bin_dir)
    bin_dir.mkdir()
    for name in (
        "sha256sum",
        "stat",
        "mktemp",
        "cp",
        "cmp",
        "mkdir",
        "rm",
        "grep",
        "awk",
        "readlink",
        "chmod",
        "cat",
        "mv",
        "dirname",
        "basename",
        "curl",
        "sudo",
    ):
        if shutil.which(name):
            _link_tool(bin_dir, name)
    if install_text is None:
        _link_tool(bin_dir, "install")
    else:
        _write_executable(bin_dir / "install", install_text)
    if udevadm is not None:
        _write_executable(bin_dir / "udevadm", udevadm)
    if include_python:
        _link_tool(bin_dir, "python3")
    return bin_dir


def _dest_tree(tmp_path: Path, *, power: bool = False) -> Path:
    dest = tmp_path / "dest"
    (dest / "etc" / "udev" / "rules.d").mkdir(parents=True)
    if power:
        (dest / "usr" / "local" / "bin").mkdir(parents=True)
        (dest / "etc" / "polkit-1" / "rules.d").mkdir(parents=True)
        (dest / "usr" / "share" / "polkit-1" / "actions").mkdir(parents=True)
    return dest


def _apply(
    tmp_path: Path,
    dest: Path,
    *,
    reactive: int = 0,
    power: int = 0,
    hash_file: Path | None = None,
    payload: Path | None = None,
    udevadm_status: int = 0,
    install_text: str | None = None,
    include_python: bool = True,
    include_udevadm: bool = True,
) -> subprocess.CompletedProcess[str]:
    log = tmp_path / "udevadm.log"
    if include_udevadm:
        udevadm = f"#!/bin/bash\nprintf '%s\\n' \"$*\" >> '{log}'\nexit {udevadm_status}\n"
    else:
        udevadm = None
    bin_dir = _tool_path(
        tmp_path,
        udevadm=udevadm,
        include_python=include_python,
        install_text=install_text,
    )
    payload_dir = payload or _SYSTEM
    hash_arg = str(hash_file) if hash_file is not None else ""
    script = f"""
    set -euo pipefail
    source "{_LIB}"
    hardware_access_apply "{payload_dir}" "{dest}" "{reactive}" "{power}" "{hash_arg}"
    """
    return _run(script, env={"PATH": str(bin_dir)})


def _result_line(completed: subprocess.CompletedProcess[str]) -> str:
    lines = [line for line in completed.stdout.splitlines() if line.startswith("keyrgb-hardware-access:")]
    assert lines, f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    return lines[-1]


def test_keyboard_only_installs_shipped_rules_and_reloads(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    completed = _apply(tmp_path, dest)

    assert completed.returncode == 0, completed.stderr
    assert _result_line(completed) == "keyrgb-hardware-access: installed"
    usb = dest / "etc/udev/rules.d/99-ite8291-wootbook.rules"
    sysfs = dest / "etc/udev/rules.d/99-keyrgb-sysfs-leds.rules"
    assert usb.read_bytes() == (_SYSTEM / _USB_REL).read_bytes()
    assert sysfs.read_bytes() == (_SYSTEM / _SYSFS_REL).read_bytes()
    assert stat.S_IMODE(usb.stat().st_mode) == 0o644
    assert stat.S_IMODE(sysfs.stat().st_mode) == 0o644
    assert not (dest / "etc/udev/rules.d/99-keyrgb-input-uaccess.rules").exists()
    assert not (dest / "usr/local/bin/keyrgb-power-helper").exists()
    reload_log = (tmp_path / "udevadm.log").read_text(encoding="utf-8")
    assert "control --reload-rules" in reload_log
    assert "sudo" not in reload_log


def test_explicit_reactive_and_power_options_install_only_when_selected(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path, power=True)
    completed = _apply(tmp_path, dest, reactive=1, power=1)

    assert completed.returncode == 0, completed.stderr
    assert (dest / "etc/udev/rules.d/99-keyrgb-input-uaccess.rules").read_bytes() == (_SYSTEM / _INPUT_REL).read_bytes()
    helper = dest / "usr/local/bin/keyrgb-power-helper"
    assert helper.read_bytes() == (_SYSTEM / _HELPER_REL).read_bytes()
    assert helper.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")
    assert stat.S_IMODE(helper.stat().st_mode) == 0o755
    assert (dest / "etc/polkit-1/rules.d/90-keyrgb-power-helper.rules").read_bytes() == (
        _SYSTEM / _POLKIT_RULE_REL
    ).read_bytes()
    assert (dest / "usr/share/polkit-1/actions/org.keyrgb.power-helper.policy").read_bytes() == (
        _SYSTEM / _POLKIT_ACTION_REL
    ).read_bytes()


def test_environment_defaults_do_not_select_optional_components(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path, power=True)
    completed = _apply(tmp_path, dest)
    assert completed.returncode == 0, completed.stderr
    assert not (dest / "usr/local/bin/keyrgb-power-helper").exists()

    sudo_log = tmp_path / "sudo.log"
    bin_dir = tmp_path / "sudo-bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "sudo",
        f"#!/bin/bash\nprintf '%s\\n' \"$*\" > '{sudo_log}'\nexit 0\n",
    )
    completed = _run(
        f"'{_ENTRY}' --payload-dir '{_SYSTEM}'",
        env={
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "KEYRGB_INSTALL_POWER_HELPER": "y",
            "KEYRGB_INSTALL_INPUT_UDEV": "y",
        },
    )
    assert completed.returncode == 0, completed.stderr
    sudo_text = sudo_log.read_text(encoding="utf-8")
    assert "--payload-dir" in sudo_text
    assert "--power-controls" not in sudo_text
    assert "--reactive-input" not in sudo_text
    assert "/etc/udev" not in completed.stdout


def test_missing_udevadm_writes_nothing(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    completed = _apply(tmp_path, dest, include_udevadm=False)

    assert completed.returncode == 10, completed.stderr
    assert _result_line(completed) == "keyrgb-hardware-access: prerequisite missing-udevadm"
    assert not (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").exists()
    assert completed.returncode not in {126, 127}


def test_unwritable_power_destination_does_not_block_udev_retry(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    blocked = _apply(tmp_path, dest, power=1)

    assert blocked.returncode == 10, blocked.stderr
    assert "unwritable-destination" in _result_line(blocked)
    assert not (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").exists()

    retry = _apply(tmp_path, dest, power=0)
    assert retry.returncode == 0, retry.stderr
    assert (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").is_file()
    assert not (dest / "usr/local/bin/keyrgb-power-helper").exists()


def test_missing_python3_blocks_power_controls_before_writes(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path, power=True)
    completed = _apply(tmp_path, dest, power=1, include_python=False)

    assert completed.returncode == 10, completed.stderr
    assert "missing-python3" in _result_line(completed)
    assert not (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").exists()
    assert not (dest / "usr/local/bin/keyrgb-power-helper").exists()


def test_foreign_destination_conflicts_before_any_write(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    foreign = dest / "etc/udev/rules.d/99-ite8291-wootbook.rules"
    foreign.write_text("# vendor rules, not KeyRGB\n", encoding="utf-8")

    completed = _apply(tmp_path, dest)

    assert completed.returncode == 11, completed.stderr
    assert "conflict" in _result_line(completed)
    assert str(foreign) in _result_line(completed)
    assert foreign.read_text(encoding="utf-8").startswith("# vendor")
    assert not (dest / "etc/udev/rules.d/99-keyrgb-sysfs-leds.rules").exists()


def test_legacy_managed_rule_is_updated_in_place(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    legacy = dest / "etc/udev/rules.d/99-ite8291-wootbook.rules"
    legacy.write_text('# Allow user access to ITE 8291 USB device.\nSUBSYSTEM=="usb"\n', encoding="utf-8")

    completed = _apply(tmp_path, dest)

    assert completed.returncode == 0, completed.stderr
    assert legacy.read_bytes() == (_SYSTEM / _USB_REL).read_bytes()


def test_repeat_run_does_not_rewrite_identical_files(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    first = _apply(tmp_path, dest)
    assert first.returncode == 0, first.stderr

    counter = tmp_path / "install.count"
    counter.write_text("0", encoding="utf-8")
    install_text = f"""#!/bin/bash
count=$(cat '{counter}')
echo $((count + 1)) > '{counter}'
exec /usr/bin/install "$@"
"""
    second = _apply(tmp_path, dest, install_text=install_text)

    assert second.returncode == 0, second.stderr
    assert counter.read_text(encoding="utf-8").strip() == "0"


def test_hash_mismatch_writes_nothing(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    hash_file = tmp_path / "hashes.txt"
    hash_file.write_text(
        f"{_USB_REL}={'0' * 64}\n{_SYSFS_REL}={_sha256(_SYSTEM / _SYSFS_REL)}\n",
        encoding="utf-8",
    )

    completed = _apply(tmp_path, dest, hash_file=hash_file)

    assert completed.returncode == 12, completed.stderr
    assert _result_line(completed) == "keyrgb-hardware-access: failed hash-mismatch written=none"
    assert not (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").exists()


def test_matching_sha256_allows_install(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    hash_file = tmp_path / "hashes.txt"
    hash_file.write_text(
        f"{_USB_REL}={_sha256(_SYSTEM / _USB_REL)}\n{_SYSFS_REL}={_sha256(_SYSTEM / _SYSFS_REL)}\n",
        encoding="utf-8",
    )

    completed = _apply(tmp_path, dest, hash_file=hash_file)

    assert completed.returncode == 0, completed.stderr
    assert (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").is_file()


def test_unsafe_payload_mode_is_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    shutil.copytree(_SYSTEM / "udev", payload / "udev")
    unsafe = payload / _USB_REL
    unsafe.chmod(0o666)
    dest = _dest_tree(tmp_path)

    completed = _apply(tmp_path, dest, payload=payload)

    assert completed.returncode == 10, completed.stderr
    assert "unsafe-payload" in _result_line(completed)
    assert not (dest / "etc/udev/rules.d/99-keyrgb-sysfs-leds.rules").exists()


def test_symlink_payload_is_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    (payload / "udev").mkdir(parents=True)
    shutil.copy2(_SYSTEM / _SYSFS_REL, payload / _SYSFS_REL)
    (payload / _USB_REL).symlink_to(_SYSTEM / _USB_REL)
    dest = _dest_tree(tmp_path)

    completed = _apply(tmp_path, dest, payload=payload)

    assert completed.returncode == 10, completed.stderr
    assert "bad-payload-dir" in _result_line(completed) or "missing-payload" in _result_line(completed)
    assert list((dest / "etc/udev/rules.d").iterdir()) == []


def test_partial_install_stops_and_reports_written_file(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    counter = tmp_path / "install.count"
    counter.write_text("0", encoding="utf-8")
    install_text = f"""#!/bin/bash
count=$(cat '{counter}')
next=$((count + 1))
echo "$next" > '{counter}'
if [ "$next" -ge 2 ]; then
  echo "forced install failure" >&2
  exit 1
fi
exec /usr/bin/install "$@"
"""
    completed = _apply(tmp_path, dest, install_text=install_text)

    assert completed.returncode == 12, completed.stderr
    result = _result_line(completed)
    assert result.startswith("keyrgb-hardware-access: failed install written=")
    assert "99-ite8291-wootbook.rules" in result
    assert (dest / "etc/udev/rules.d/99-ite8291-wootbook.rules").is_file()
    assert not (dest / "etc/udev/rules.d/99-keyrgb-sysfs-leds.rules").exists()
    assert not (tmp_path / "udevadm.log").exists()


def test_reload_failure_reports_written_files(tmp_path: Path) -> None:
    dest = _dest_tree(tmp_path)
    completed = _apply(tmp_path, dest, udevadm_status=1)

    assert completed.returncode == 12, completed.stderr
    result = _result_line(completed)
    assert "failed reload written=" in result
    assert "99-ite8291-wootbook.rules" in result
    assert "99-keyrgb-sysfs-leds.rules" in result
