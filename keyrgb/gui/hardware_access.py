"""Unprivileged hardware-access setup handoff.

Resolves the bundled or checkout payload, stages it outside any AppImage mount,
and authorizes one ``pkexec`` run of a fixed verifier. This module does not
build a window and does not download rules.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from keyrgb.core.runtime.imports import repo_root_from
from keyrgb.gui.hardware_access_verifier import VERIFIER, is_pkexec_stderr

APPDIR_RELATIVE = "usr/lib/keyrgb/hardware-access"
RESULT_PREFIX = "keyrgb-hardware-access:"

_ENTRYPOINT = "install_hardware_access.sh"
_LIBRARY = "lib/hardware_access.sh"
_MATCH = "lib/uninstall_match.sh"
_USB = "system/udev/99-ite8291-wootbook.rules"
_SYSFS = "system/udev/99-keyrgb-sysfs-leds.rules"
_INPUT = "system/udev/99-keyrgb-input-uaccess.rules"
_HELPER = "system/bin/keyrgb-power-helper"
_POLKIT_RULE = "system/polkit/90-keyrgb-power-helper.rules"
_POLKIT_ACTION = "system/polkit/org.keyrgb.power-helper.policy"
_KEYBOARD_FILES = (_USB, _SYSFS)
_POWER_FILES = (_HELPER, _POLKIT_RULE, _POLKIT_ACTION)


@dataclass(frozen=True, slots=True)
class HardwareAccessRequest:
    """Explicit component selection. Environment defaults are ignored."""

    reactive_input: bool = False
    power_controls: bool = False


@dataclass(frozen=True, slots=True)
class HardwareAccessBundle:
    """Resolved on-disk layout. ``payload_dir`` is the ``system/`` tree."""

    entrypoint: Path
    library: Path
    match_helper: Path
    payload_dir: Path


@dataclass(frozen=True, slots=True)
class HardwareAccessOutcome:
    """Classified result. ``written`` is None when the write state is unknown."""

    outcome: str
    detail: str
    written: str | None
    returncode: int
    stdout: str
    stderr: str
    terminal_command: str


def terminal_command(request: HardwareAccessRequest) -> str:
    """Terminal fallback. Does not include a download URL."""

    parts = ["install.sh", "--hardware-access-only"]
    if request.reactive_input:
        parts.append("--reactive-input")
    if request.power_controls:
        parts.append("--power-controls")
    return " ".join(parts)


def resolve_hardware_access_bundle(
    *,
    environ: Mapping[str, str] | None = None,
    anchor: str | Path | None = None,
) -> HardwareAccessBundle:
    """Return the AppImage bundle, or the checkout tree when ``APPDIR`` is unset.

    A set ``APPDIR`` that does not contain the bundle is an error. Do not fall
    back to a developer checkout from inside an AppImage.
    """

    env = os.environ if environ is None else environ
    appdir = env.get("APPDIR", "").strip()
    if appdir:
        return _bundle_from_root(Path(appdir) / APPDIR_RELATIVE, payload_name="system")
    root = repo_root_from(anchor or __file__)
    entrypoint = root / "scripts" / _ENTRYPOINT
    library = root / "scripts" / _LIBRARY
    match_helper = root / "scripts" / _MATCH
    payload_dir = root / "system"
    bundle = HardwareAccessBundle(
        entrypoint=entrypoint,
        library=library,
        match_helper=match_helper,
        payload_dir=payload_dir,
    )
    _require_bundle(bundle)
    return bundle


def selected_payload_files(request: HardwareAccessRequest) -> tuple[str, ...]:
    files = list(_KEYBOARD_FILES)
    if request.reactive_input:
        files.append(_INPUT)
    if request.power_controls:
        files.extend(_POWER_FILES)
    return tuple(files)


def sha256_file(path: Path) -> str:
    """Return the lowercase hex digest ``sha256sum`` would print."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_pkexec_argv(
    staged: Mapping[str, Path],
    *,
    payload_dir: Path,
    request: HardwareAccessRequest,
    pkexec: str,
) -> list[str]:
    """Build one ``pkexec`` invocation. Paths are arguments, not script text."""

    payload_hashes = _payload_hash_args(payload_dir, request)
    return [
        pkexec,
        "--disable-internal-agent",
        "/bin/sh",
        "-c",
        VERIFIER,
        "_",
        str(staged[_ENTRYPOINT]),
        sha256_file(staged[_ENTRYPOINT]),
        str(staged[_LIBRARY]),
        sha256_file(staged[_LIBRARY]),
        str(staged[_MATCH]),
        sha256_file(staged[_MATCH]),
        str(payload_dir),
        "1" if request.reactive_input else "0",
        "1" if request.power_controls else "0",
        *payload_hashes,
    ]


def classify_hardware_access_result(
    *,
    returncode: int,
    stdout: str,
    stderr: str,
) -> tuple[str, str, str | None]:
    """Map a process result to the setup contract.

    A worker result line wins over the exit status. Exit 126 with no result
    line is cancellation. Exit 127 is an authorization failure only when stderr
    is pkexec's own message. Any other missing result is ``failed`` with an
    unknown write state.
    """

    line = _last_result_line(stdout)
    if line is not None:
        return _parse_result_line(line)
    if returncode == 126:
        return ("cancelled", "dismissed", "none")
    if returncode == 127 and _is_pkexec_stderr(stderr):
        return ("authorization-failed", "pkexec", "none")
    return ("failed", "missing-result", None)


def run_hardware_access(
    request: HardwareAccessRequest,
    *,
    environ: Mapping[str, str] | None = None,
    anchor: str | Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> HardwareAccessOutcome:
    """Stage the payload and run one authorization, or return a preflight result.

    ``runner`` is the process boundary. Tests pass a fake. The default runner
    executes ``pkexec`` and does not use a shell.
    """

    command = terminal_command(request)
    if request.power_controls and which("python3") is None:
        return _preflight("missing-python3", command)
    pkexec = which("pkexec")
    if pkexec is None:
        return _preflight("missing-pkexec", command)
    try:
        bundle = resolve_hardware_access_bundle(environ=environ, anchor=anchor)
    except OSError as exc:
        return _preflight(f"missing-payload {exc}", command)
    try:
        with tempfile.TemporaryDirectory(prefix="keyrgb-hardware-access-") as raw_stage:
            stage = Path(raw_stage)
            os.chmod(stage, 0o700)
            staged = _stage_files(bundle, request, stage)
            argv = build_pkexec_argv(
                staged,
                payload_dir=stage / "system",
                request=request,
                pkexec=pkexec,
            )
            completed = _default_runner(argv) if runner is None else runner(argv)
    except OSError as exc:
        return _preflight(f"stage-failed {exc}", command)
    outcome, detail, written = classify_hardware_access_result(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    return HardwareAccessOutcome(
        outcome=outcome,
        detail=detail,
        written=written,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        terminal_command=command,
    )


def _bundle_from_root(root: Path, *, payload_name: str) -> HardwareAccessBundle:
    bundle = HardwareAccessBundle(
        entrypoint=root / _ENTRYPOINT,
        library=root / _LIBRARY,
        match_helper=root / _MATCH,
        payload_dir=root / payload_name,
    )
    _require_bundle(bundle)
    return bundle


def _require_bundle(bundle: HardwareAccessBundle) -> None:
    required = (
        bundle.entrypoint,
        bundle.library,
        bundle.match_helper,
        bundle.payload_dir / _USB.removeprefix("system/"),
        bundle.payload_dir / _SYSFS.removeprefix("system/"),
    )
    for path in required:
        if path.is_symlink() or not path.is_file():
            raise OSError(f"hardware-access payload is incomplete: {path}")


def _stage_files(bundle: HardwareAccessBundle, request: HardwareAccessRequest, stage: Path) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    copies = {
        _ENTRYPOINT: bundle.entrypoint,
        _LIBRARY: bundle.library,
        _MATCH: bundle.match_helper,
    }
    for relative, source in copies.items():
        staged[relative] = _copy_private(source, stage / relative)
    for relative in selected_payload_files(request):
        _copy_private(bundle.payload_dir / relative, stage / "system" / relative.removeprefix("system/"))
    return staged


def _copy_private(source: Path, dest: Path) -> Path:
    if source.is_symlink() or not source.is_file():
        raise OSError(f"refusing to stage unsafe hardware-access file: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    dest.chmod(0o600)
    return dest


def _payload_hash_args(payload_dir: Path, request: HardwareAccessRequest) -> list[str]:
    args: list[str] = []
    for relative in selected_payload_files(request):
        rel = relative.removeprefix("system/")
        digest = sha256_file(payload_dir / rel)
        if len(digest) != 64:
            raise OSError(f"refusing non-sha256 digest for {relative}")
        args.extend((rel, digest))
    return args


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), check=False, text=True, capture_output=True)


def _preflight(detail: str, command: str) -> HardwareAccessOutcome:
    return HardwareAccessOutcome(
        outcome="prerequisite",
        detail=detail,
        written="none",
        returncode=10,
        stdout=f"{RESULT_PREFIX} prerequisite {detail}\n",
        stderr="",
        terminal_command=command,
    )


def _last_result_line(stdout: str) -> str | None:
    found: str | None = None
    for line in stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            found = line.strip()
    return found


def _parse_result_line(line: str) -> tuple[str, str, str | None]:
    body = line[len(RESULT_PREFIX) :].strip()
    outcome, _, rest = body.partition(" ")
    written: str | None = None
    detail = rest
    marker = "written="
    if marker in rest:
        before, _, written = rest.partition(marker)
        detail = before.strip()
        written = written.strip() or None
    elif outcome in {"prerequisite", "conflict", "cancelled", "authorization-failed"}:
        written = "none"
    return outcome, detail, written


def _is_pkexec_stderr(stderr: str) -> bool:
    return is_pkexec_stderr(stderr)
