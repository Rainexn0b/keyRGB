from __future__ import annotations

import argparse
import os
import shlex
import shutil
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import Protocol, TextIO

from keyrgb.core.runtime.imports import repo_root_from

RUNTIME_LOG_NAME = "keyrgb-debug.log"
RUNTIME_LOG_MODES = ("debug", "brightness", "full")
RUNTIME_LAUNCHERS = ("installed", "source")

_DEBUG_ENV_KEYS = (
    "KEYRGB_DEBUG",
    "KEYRGB_DEBUG_BRIGHTNESS",
    "KEYRGB_DEBUG_REACTIVE_INPUT",
)
_MODE_ENV: dict[str, dict[str, str]] = {
    "debug": {"KEYRGB_DEBUG": "1"},
    "brightness": {
        "KEYRGB_DEBUG": "1",
        "KEYRGB_DEBUG_BRIGHTNESS": "1",
    },
    "full": {
        "KEYRGB_DEBUG": "1",
        "KEYRGB_DEBUG_BRIGHTNESS": "1",
        "KEYRGB_DEBUG_REACTIVE_INPUT": "1",
    },
}


class RuntimeLogCaptureError(RuntimeError):
    """Raised when the requested KeyRGB runtime cannot be launched."""


class _RuntimeProcess(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def wait(self) -> int: ...


def _is_source_root(path: Path) -> bool:
    try:
        return (path / "pyproject.toml").is_file() and (path / "src" / "tray").is_dir()
    except OSError:
        return False


def discover_source_root() -> Path | None:
    """Return the current KeyRGB checkout when capture runs from source."""

    candidates: list[Path] = []
    try:
        candidates.append(Path.cwd())
    except OSError:
        pass
    candidates.append(repo_root_from(__file__))

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_source_root(resolved):
            return resolved
    return None


def _launcher_is_inside_source(launcher_path: Path, source_root: Path | None) -> bool:
    if source_root is None:
        return False
    try:
        launcher_path.relative_to(source_root.resolve())
    except ValueError:
        return False
    return True


def _runtime_launcher_candidates() -> list[Path]:
    candidates: list[Path] = []
    first_launcher = shutil.which("keyrgb")
    if first_launcher is not None:
        candidates.append(Path(first_launcher).resolve())

    for path_entry in os.get_exec_path():
        candidate = Path(path_entry) / "keyrgb"
        try:
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                continue
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates


def _installed_runtime_command(source_root: Path | None) -> list[str]:
    found_source_launcher = False
    for launcher_path in _runtime_launcher_candidates():
        if _launcher_is_inside_source(launcher_path, source_root):
            found_source_launcher = True
            continue
        return [str(launcher_path)]

    if found_source_launcher:
        raise RuntimeLogCaptureError(
            "Every 'keyrgb' launcher on PATH resolves inside this source checkout and would reuse "
            "the development environment."
        )
    raise RuntimeLogCaptureError("No installed 'keyrgb' launcher was found on PATH.")


def _runtime_command(*, launcher: str, source_root: Path | None) -> list[str]:
    if launcher == "installed":
        return _installed_runtime_command(source_root)
    if launcher == "source":
        if source_root is None:
            raise RuntimeLogCaptureError(
                "No KeyRGB source checkout was detected. Run from the checkout or select the installed launcher."
            )
        try:
            # Keep checkout code authoritative while an external AppImage or
            # installation supplies its desktop-native runtime dependencies.
            return _installed_runtime_command(source_root)
        except RuntimeLogCaptureError:
            return [sys.executable, "-B", "-u", "-m", "keyrgb.tray"]
    raise RuntimeLogCaptureError(f"Unknown runtime log launcher: {launcher!r}")


def _runtime_environment(
    *,
    mode: str,
    environ: Mapping[str, str] | None = None,
    source_root: Path | None = None,
) -> dict[str, str]:
    try:
        mode_env = _MODE_ENV[mode]
    except KeyError as exc:
        raise RuntimeLogCaptureError(f"Unknown runtime log mode: {mode!r}") from exc

    env = dict(os.environ if environ is None else environ)
    for key in _DEBUG_ENV_KEYS:
        env.pop(key, None)
    env.update(mode_env)
    env["PYTHONUNBUFFERED"] = "1"
    if source_root is not None:
        source_path = str(source_root.resolve())
        inherited_pythonpath = str(env.get("PYTHONPATH") or "").strip()
        env["PYTHONPATH"] = os.pathsep.join(part for part in (source_path, inherited_pythonpath) if part)
    return env


def _runtime_working_directory(*, launcher: str, command: list[str], source_root: Path | None) -> Path:
    if launcher == "source":
        assert source_root is not None
        # Python's module launcher checks cwd before the AppImage's bundled
        # package path, making the current checkout authoritative.
        return source_root.resolve()
    return Path(command[0]).resolve().parent


def _normalize_exit_code(returncode: int) -> int:
    if returncode < 0:
        return 128 + abs(int(returncode))
    return int(returncode)


def _wait_with_signal_forwarding(process: _RuntimeProcess) -> int:
    forwarded_signals = (signal.SIGINT, signal.SIGTERM)
    previous_handlers = {signum: signal.getsignal(signum) for signum in forwarded_signals}

    def _forward(signum: int, _frame: FrameType | None) -> None:
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            return

    try:
        for signum in forwarded_signals:
            signal.signal(signum, _forward)
        return _normalize_exit_code(process.wait())
    finally:
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)


def _write_capture_header(
    log_file: TextIO,
    *,
    mode: str,
    launcher: str,
    command: list[str],
    working_directory: Path,
    source_root: Path | None,
    env: Mapping[str, str],
) -> None:
    enabled_flags = " ".join(f"{key}={env[key]}" for key in _DEBUG_ENV_KEYS if key in env)
    log_file.write("KeyRGB runtime log capture\n")
    log_file.write(f"started_utc={datetime.now(timezone.utc).isoformat()}\n")
    log_file.write(f"mode={mode}\n")
    log_file.write(f"launcher={launcher}\n")
    log_file.write(f"command={shlex.join(command)}\n")
    log_file.write(f"working_directory={working_directory}\n")
    if source_root is not None:
        log_file.write(f"source_root={source_root}\n")
    log_file.write(f"debug_env={enabled_flags}\n")
    log_file.write("--- KeyRGB output ---\n")
    log_file.flush()


def capture_runtime_log(
    *,
    mode: str,
    launcher: str,
    output_directory: Path | None = None,
    source_root: Path | None = None,
) -> int:
    """Run KeyRGB in the foreground and capture merged diagnostic output."""

    try:
        output_root = (Path.cwd() if output_directory is None else output_directory).resolve()
        resolved_source_root = source_root.resolve() if source_root is not None else discover_source_root()
        log_path = output_root / RUNTIME_LOG_NAME
        command = _runtime_command(launcher=launcher, source_root=resolved_source_root)
        working_directory = _runtime_working_directory(
            launcher=launcher,
            command=command,
            source_root=resolved_source_root,
        )
        env = _runtime_environment(
            mode=mode,
            source_root=resolved_source_root if launcher == "source" else None,
        )
        print(f"Capturing KeyRGB {mode} runtime logs to: {log_path}")
        print(f"Runtime launcher: {command[0]}")
        print(f"Runtime working directory: {working_directory}")
        print("Quit any existing KeyRGB tray instance first. Stop this capture with Ctrl-C.")

        with log_path.open("w", encoding="utf-8") as log_file:
            _write_capture_header(
                log_file,
                mode=mode,
                launcher=launcher,
                command=command,
                working_directory=working_directory,
                source_root=resolved_source_root if launcher == "source" else None,
                env=env,
            )
            process = subprocess.Popen(
                command,
                cwd=str(working_directory),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            exit_code = _wait_with_signal_forwarding(process)
    except (OSError, RuntimeLogCaptureError) as exc:
        print(f"Runtime log capture failed: {exc}", file=sys.stderr)
        return 2

    print(f"KeyRGB runtime exited with status {exit_code}. Log saved to: {log_path}")
    return exit_code


def add_runtime_capture_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--capture-runtime-log",
        nargs="?",
        const="full",
        choices=RUNTIME_LOG_MODES,
        metavar="MODE",
        help="Capture KeyRGB runtime logs (debug, brightness, or full; default: full)",
    )
    parser.add_argument(
        "--runtime-log-launcher",
        choices=RUNTIME_LAUNCHERS,
        default="installed",
        help="Runtime used by --capture-runtime-log (default: installed)",
    )


def capture_runtime_log_from_cli(argv: Sequence[str], *, prog: str = "keyrgb") -> int | None:
    """Handle capture-only runtime arguments, or return ``None`` for a normal tray launch."""

    capture_option_present = any(
        arg == "--capture-runtime-log" or arg.startswith("--capture-runtime-log=") for arg in argv
    )
    launcher_option_present = any(
        arg == "--runtime-log-launcher" or arg.startswith("--runtime-log-launcher=") for arg in argv
    )
    if not capture_option_present and not launcher_option_present:
        return None

    parser = argparse.ArgumentParser(prog=prog, description="Capture a KeyRGB runtime diagnostic log.")
    add_runtime_capture_arguments(parser)
    args = parser.parse_args(list(argv))
    if args.capture_runtime_log is None:
        parser.error("--runtime-log-launcher requires --capture-runtime-log")
    return capture_runtime_log(
        mode=str(args.capture_runtime_log),
        launcher=str(args.runtime_log_launcher),
    )


__all__ = [
    "RUNTIME_LAUNCHERS",
    "RUNTIME_LOG_MODES",
    "RUNTIME_LOG_NAME",
    "RuntimeLogCaptureError",
    "add_runtime_capture_arguments",
    "capture_runtime_log",
    "capture_runtime_log_from_cli",
    "discover_source_root",
]
