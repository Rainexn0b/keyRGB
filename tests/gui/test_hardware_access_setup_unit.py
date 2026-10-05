from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path

from keyrgb.gui import hardware_access as setup

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(**kwargs: bool) -> setup.HardwareAccessRequest:
    return setup.HardwareAccessRequest(**kwargs)


def test_checkout_resolution_does_not_require_appdir(monkeypatch) -> None:
    monkeypatch.delenv("APPDIR", raising=False)
    bundle = setup.resolve_hardware_access_bundle(environ={}, anchor=_REPO_ROOT / "keyrgb/gui/hardware_access.py")

    assert bundle.entrypoint == _REPO_ROOT / "scripts/install_hardware_access.sh"
    assert bundle.library == _REPO_ROOT / "scripts/lib/hardware_access.sh"
    assert bundle.match_helper == _REPO_ROOT / "scripts/lib/uninstall_match.sh"
    assert (bundle.payload_dir / "udev/99-ite8291-wootbook.rules").is_file()


def test_appdir_resolution_does_not_fall_back_to_checkout(tmp_path: Path) -> None:
    appdir = tmp_path / "mount"
    bundle_root = appdir / setup.APPDIR_RELATIVE
    (bundle_root / "lib").mkdir(parents=True)
    (bundle_root / "system/udev").mkdir(parents=True)
    for name in ("install_hardware_access.sh",):
        (bundle_root / name).write_text("entrypoint\n", encoding="utf-8")
    (bundle_root / "lib/hardware_access.sh").write_text("lib\n", encoding="utf-8")
    (bundle_root / "lib/uninstall_match.sh").write_text("match\n", encoding="utf-8")
    (bundle_root / "system/udev/99-ite8291-wootbook.rules").write_text("usb\n", encoding="utf-8")
    (bundle_root / "system/udev/99-keyrgb-sysfs-leds.rules").write_text("sysfs\n", encoding="utf-8")

    bundle = setup.resolve_hardware_access_bundle(environ={"APPDIR": str(appdir)})

    assert bundle.entrypoint == bundle_root / "install_hardware_access.sh"
    assert bundle.payload_dir == bundle_root / "system"


def test_incomplete_appdir_is_not_a_checkout_fallback(tmp_path: Path) -> None:
    appdir = tmp_path / "mount"
    appdir.mkdir()
    try:
        setup.resolve_hardware_access_bundle(environ={"APPDIR": str(appdir)})
    except OSError as exc:
        assert "incomplete" in str(exc)
    else:
        raise AssertionError("incomplete AppImage bundle was accepted")


def test_module_has_no_network_url() -> None:
    text = Path(setup.__file__).read_text(encoding="utf-8")
    executable = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    assert "raw.githubusercontent.com" not in executable
    assert "github.com" not in executable
    assert "sudo" not in setup.VERIFIER
    assert "curl" not in setup.VERIFIER
    assert "--keep-cwd" not in setup.VERIFIER


def test_pkexec_argv_keeps_paths_out_of_the_script(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    (stage / "lib").mkdir(parents=True)
    (stage / "system/udev").mkdir(parents=True)
    entry = stage / "install_hardware_access.sh"
    library = stage / "lib/hardware_access.sh"
    match = stage / "lib/uninstall_match.sh"
    rule = stage / "system/udev/99-ite8291-wootbook.rules"
    sysfs = stage / "system/udev/99-keyrgb-sysfs-leds.rules"
    for path, text in (
        (entry, "entry\n"),
        (library, "lib\n"),
        (match, "match\n"),
        (rule, "usb\n"),
        (sysfs, "sysfs\n"),
    ):
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)
    staged = {
        "install_hardware_access.sh": entry,
        "lib/hardware_access.sh": library,
        "lib/uninstall_match.sh": match,
    }

    argv = setup.build_pkexec_argv(
        staged,
        payload_dir=stage / "system",
        request=_request(),
        pkexec="/usr/bin/pkexec",
    )

    assert argv[:5] == ["/usr/bin/pkexec", "--disable-internal-agent", "/bin/sh", "-c", setup.VERIFIER]
    assert "--keep-cwd" not in argv
    assert argv[5] == "_"
    assert str(entry) in argv[6:]
    assert str(entry) not in setup.VERIFIER
    assert _sha256(rule) in argv
    assert "udev/99-ite8291-wootbook.rules" in argv
    assert "--power-controls" not in argv
    assert "bin/keyrgb-power-helper" not in argv


def test_missing_pkexec_and_python_do_not_launch(monkeypatch) -> None:
    calls: list[list[str]] = []

    def runner(argv: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))  # type: ignore[arg-type]
        raise AssertionError("runner should not be called")

    missing_pkexec = setup.run_hardware_access(
        _request(),
        environ={},
        anchor=_REPO_ROOT / "keyrgb/gui/hardware_access.py",
        which=lambda name: None if name == "pkexec" else "/usr/bin/python3",
        runner=runner,
    )
    assert missing_pkexec.outcome == "prerequisite"
    assert missing_pkexec.written == "none"
    assert "missing-pkexec" in missing_pkexec.detail
    assert "install.sh --hardware-access-only" in missing_pkexec.terminal_command

    missing_python = setup.run_hardware_access(
        _request(power_controls=True),
        environ={},
        anchor=_REPO_ROOT / "keyrgb/gui/hardware_access.py",
        which=lambda name: None if name == "python3" else "/usr/bin/pkexec",
        runner=runner,
    )
    assert missing_python.outcome == "prerequisite"
    assert "missing-python3" in missing_python.detail
    assert calls == []
    monkeypatch.undo()


def test_wrapper_classifies_pkexec_and_worker_results() -> None:
    cancelled = setup.classify_hardware_access_result(returncode=126, stdout="", stderr="")
    assert cancelled == ("cancelled", "dismissed", "none")

    denied = setup.classify_hardware_access_result(
        returncode=127,
        stdout="",
        stderr="Error executing command as another user: Not authorized\n",
    )
    assert denied[0] == "authorization-failed"
    assert denied[2] == "none"

    no_agent = setup.classify_hardware_access_result(
        returncode=127,
        stdout="",
        stderr="Error executing command as another user: No authentication agent found.\n",
    )
    assert no_agent[0] == "authorization-failed"

    unknown = setup.classify_hardware_access_result(returncode=127, stdout="", stderr="bash: missing\n")
    assert unknown[0] == "failed"
    assert unknown[2] is None

    worker = setup.classify_hardware_access_result(
        returncode=127,
        stdout="keyrgb-hardware-access: failed install written=/etc/udev/rules.d/99-ite8291-wootbook.rules\n",
        stderr="Error executing command as another user: Not authorized\n",
    )
    assert worker[0] == "failed"
    assert worker[2] == "/etc/udev/rules.d/99-ite8291-wootbook.rules"


def test_verifier_executes_hashed_copy_not_staged_script(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    staged = tmp_path / "staged.sh"
    library = tmp_path / "lib.sh"
    match = tmp_path / "match.sh"
    payload = tmp_path / "payload"
    payload.mkdir()
    rule = payload / "udev/99-ite8291-wootbook.rules"
    rule.parent.mkdir()
    rule.write_text("usb\n", encoding="utf-8")
    sysfs = payload / "udev/99-keyrgb-sysfs-leds.rules"
    sysfs.write_text("sysfs\n", encoding="utf-8")
    staged.write_text(
        f"#!/bin/bash\nprintf '%s\\n' \"$0\" \"$@\" > '{marker}'\nexit 0\n",
        encoding="utf-8",
    )
    library.write_text("lib\n", encoding="utf-8")
    match.write_text("match\n", encoding="utf-8")
    for path in (staged, library, match, rule, sysfs):
        path.chmod(0o600)

    completed = _run_verifier(staged, library, match, payload, reactive="0", power="0")

    assert completed.returncode == 0, completed.stderr
    recorded = marker.read_text(encoding="utf-8").splitlines()
    assert recorded[0] != str(staged)
    assert recorded[0].endswith("/install_hardware_access.sh")
    assert "--payload-dir" in recorded
    assert str(payload) in recorded
    assert "--hash" in recorded
    assert "udev/99-ite8291-wootbook.rules=" in "\n".join(recorded)


def test_verifier_rejects_swapped_script_without_executing_it(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    staged = tmp_path / "staged.sh"
    library = tmp_path / "lib.sh"
    match = tmp_path / "match.sh"
    payload = tmp_path / "payload"
    payload.mkdir()
    staged.write_text("#!/bin/bash\ntouch ran\n", encoding="utf-8")
    library.write_text("lib\n", encoding="utf-8")
    match.write_text("match\n", encoding="utf-8")
    staged.chmod(0o600)
    library.chmod(0o600)
    match.chmod(0o600)

    completed = _run_verifier(
        staged,
        library,
        match,
        payload,
        reactive="0",
        power="0",
        entry_hash="0" * 64,
    )

    assert completed.returncode == 12
    assert "hash-mismatch" in completed.stdout
    assert "written=none" in completed.stdout
    assert not marker.exists()


def test_verifier_rejects_symlink_and_world_writable_code(tmp_path: Path) -> None:
    target = tmp_path / "real.sh"
    target.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    link = tmp_path / "link.sh"
    link.symlink_to(target)
    library = tmp_path / "lib.sh"
    match = tmp_path / "match.sh"
    library.write_text("lib\n", encoding="utf-8")
    match.write_text("match\n", encoding="utf-8")
    payload = tmp_path / "payload"
    payload.mkdir()

    linked = _run_verifier(link, library, match, payload, reactive="0", power="0")
    assert linked.returncode == 12
    assert "unsafe-code" in linked.stdout

    writable = tmp_path / "writable.sh"
    writable.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    writable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH | stat.S_IWOTH)
    world = _run_verifier(writable, library, match, payload, reactive="0", power="0")
    assert world.returncode == 12
    assert "unsafe-code" in world.stdout


def _run_verifier(
    entry: Path,
    library: Path,
    match: Path,
    payload: Path,
    *,
    reactive: str,
    power: str,
    entry_hash: str | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [
        "/bin/sh",
        "-c",
        setup.VERIFIER,
        "_",
        str(entry),
        entry_hash or _sha256(entry),
        str(library),
        _sha256(library),
        str(match),
        _sha256(match),
        str(payload),
        reactive,
        power,
        "udev/99-ite8291-wootbook.rules",
        _sha256(payload / "udev/99-ite8291-wootbook.rules")
        if (payload / "udev/99-ite8291-wootbook.rules").is_file()
        else "a" * 64,
        "udev/99-keyrgb-sysfs-leds.rules",
        _sha256(payload / "udev/99-keyrgb-sysfs-leds.rules")
        if (payload / "udev/99-keyrgb-sysfs-leds.rules").is_file()
        else "b" * 64,
    ]
    return subprocess.run(argv, check=False, text=True, capture_output=True, env=os.environ.copy())
