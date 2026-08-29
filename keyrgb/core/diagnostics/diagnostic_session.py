from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from keyrgb.core.diagnostics import diagnostic_session_evidence as _evidence, runtime_capture as _runtime_capture

RUNTIME_LAUNCHERS = _runtime_capture.RUNTIME_LAUNCHERS
RUNTIME_LOG_MODES = _runtime_capture.RUNTIME_LOG_MODES
RUNTIME_LOG_NAME = _runtime_capture.RUNTIME_LOG_NAME
RuntimeLogCaptureError = _runtime_capture.RuntimeLogCaptureError

DIAGNOSTIC_SESSION_DIR_NAME = "diagnostic-sessions"


def _default_diagnostic_session_root() -> Path:
    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home) if cache_home else (Path.home() / ".cache")
    return base / "keyrgb" / DIAGNOSTIC_SESSION_DIR_NAME


def _select_session_launcher(launcher: str | None, source_root: Path | None) -> str:
    """Pick the launcher used to spawn the KeyRGB child during a diagnostic session.

    Auto-selects ``source`` when invoked from a checkout, otherwise ``installed``.
    An explicit ``launcher`` override is honored (it still goes through the same
    safety checks as the runtime-log launchers, so an unsafe override simply fails
    loudly instead of launching the wrong environment).
    """

    if launcher is not None:
        return launcher
    return "source" if source_root is not None else "installed"


def _diagnostic_child_command(
    *, launcher: str, source_root: Path | None, appimage_active: bool
) -> list[str]:
    """Return the argv used to spawn the KeyRGB child for a diagnostic session.

    When running inside an AppImage (``APPIMAGE`` set) the child must use the
    current Python interpreter with ``-m keyrgb.tray`` rather than resolving
    ``keyrgb`` from PATH. Re-resolving the console script would re-mount the
    AppImage and recurse.
    """

    if appimage_active:
        return [sys.executable, "-B", "-u", "-m", "keyrgb.tray"]
    if launcher == "source":
        return [sys.executable, "-B", "-u", "-m", "keyrgb.tray"]
    return _runtime_capture._installed_runtime_command(source_root)


def _diagnostic_child_working_directory(
    *, launcher: str, command: list[str], source_root: Path | None, appimage_active: bool
) -> Path:
    if appimage_active:
        return Path.cwd().resolve()
    if launcher == "source":
        assert source_root is not None
        # Python's module launcher checks cwd before the AppImage's bundled
        # package path, making the current checkout authoritative.
        return source_root.resolve()
    return Path(command[0]).resolve().parent


def _diagnostic_child_env_source_root(
    *, launcher: str, source_root: Path | None, appimage_active: bool
) -> Path | None:
    # AppImage bundles its own package tree via PYTHONPATH; do not override it.
    if appimage_active:
        return None
    if launcher == "source":
        return source_root
    return None


def _wait_for_existing_tray_to_close() -> None:
    """Give a terminal-launched session a chance to release the singleton lock."""

    message = (
        "Close any running KeyRGB tray now so the diagnostic session can control the keyboard. "
        "Press Enter to start logging."
    )
    if sys.stdin.isatty():
        input(message + "\n")
        return
    print(message)


def run_diagnostic_session(
    *,
    mode: str = "full",
    launcher: str | None = None,
    output_dir_root: Path | None = None,
    source_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    """Run a full KeyRGB diagnostic session and return the KeyRGB child exit status.

    Creates a timestamped directory (default: ``~/.cache/keyrgb/diagnostic-sessions``)
    containing the captured runtime log, before/after diagnostics snapshots, and
    best-effort user/kernel journal slices. The directory path is printed so callers
    and desktop actions can surface it to the user.
    """

    appimage_active = bool(os.environ.get("APPIMAGE"))
    session_root = (
        _default_diagnostic_session_root() if output_dir_root is None else Path(output_dir_root).resolve()
    )
    resolved_source_root = source_root.resolve() if source_root is not None else _runtime_capture.discover_source_root()
    effective_launcher = _select_session_launcher(launcher, resolved_source_root)

    # The desktop action opens a terminal specifically so the user can close the
    # resident tray before the diagnostic child reaches the singleton lock.
    _wait_for_existing_tray_to_close()

    # One captured start time drives both the session directory timestamp and the
    # journal --since boundary so the collected slice matches the run exactly.
    session_start = datetime.now(timezone.utc)
    session_start_local = session_start.astimezone()
    timestamp = session_start.strftime("%Y%m%dT%H%M%S.%fZ")

    # Avoid two starts in the same second collapsing into one directory: the
    # microsecond component makes collisions essentially impossible, and we never
    # pass exist_ok=True — if a name is somehow taken we atomically append a suffix.
    session_dir = session_root / timestamp
    suffix = 0
    while True:
        try:
            session_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            suffix += 1
            session_dir = session_root / f"{timestamp}.{suffix}"

    log_path = session_dir / RUNTIME_LOG_NAME
    before_path = session_dir / _evidence.DIAGNOSTICS_BEFORE_NAME
    after_path = session_dir / _evidence.DIAGNOSTICS_AFTER_NAME
    journal_user_path = session_dir / _evidence.JOURNAL_USER_NAME
    journal_kernel_path = session_dir / _evidence.JOURNAL_KERNEL_NAME

    journal_since = session_start_local.strftime("%Y-%m-%d %H:%M:%S")
    journal_user_cmd = [
        "journalctl",
        "--user",
        "--no-pager",
        "--since",
        journal_since,
        "--lines",
        str(_evidence.JOURNAL_COLLECTION_LINE_LIMIT),
    ]
    journal_kernel_cmd = [
        "journalctl",
        "-k",
        "-b",
        "--no-pager",
        "--since",
        journal_since,
        "--lines",
        str(_evidence.JOURNAL_COLLECTION_LINE_LIMIT),
    ]

    # Snapshot state before launching the child so comparisons remain meaningful.
    _evidence._write_diagnostics_snapshot(before_path, when="before")

    print(f"Starting KeyRGB diagnostic session in: {session_dir}")
    print("Stop this session with Ctrl-C.")

    try:
        # Validate the launcher selection before building the child command so an
        # unsafe choice (e.g. 'source' with no detected checkout, or an unknown
        # value) fails as a handled RuntimeLogCaptureError instead of an
        # AssertionError or silently falling through to the installed launcher.
        if effective_launcher not in RUNTIME_LAUNCHERS:
            raise RuntimeLogCaptureError(
                f"Unknown diagnostic session launcher: {effective_launcher!r}"
            )
        if effective_launcher == "source" and resolved_source_root is None:
            raise RuntimeLogCaptureError(
                "No KeyRGB source checkout was detected. Run from the checkout or "
                "select the installed launcher."
            )

        command = _diagnostic_child_command(
            launcher=effective_launcher,
            source_root=resolved_source_root,
            appimage_active=appimage_active,
        )
        working_directory = _diagnostic_child_working_directory(
            launcher=effective_launcher,
            command=command,
            source_root=resolved_source_root,
            appimage_active=appimage_active,
        )
        env_source_root = _diagnostic_child_env_source_root(
            launcher=effective_launcher,
            source_root=resolved_source_root,
            appimage_active=appimage_active,
        )
        display_launcher = "appimage" if appimage_active else effective_launcher

        print(f"Runtime launcher: {command[0]} (mode={mode}, launcher={display_launcher})")

        runtime_env = _runtime_capture._runtime_environment(mode=mode, environ=env, source_root=env_source_root)

        with log_path.open("w", encoding="utf-8") as log_file:
            _runtime_capture._write_capture_header(
                log_file,
                mode=mode,
                launcher=display_launcher,
                command=command,
                working_directory=working_directory,
                source_root=env_source_root if effective_launcher == "source" else None,
                env=runtime_env,
            )
            process = subprocess.Popen(
                command,
                cwd=str(working_directory),
                env=runtime_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            exit_code = _runtime_capture._wait_with_signal_forwarding(process)
    except (OSError, RuntimeLogCaptureError) as exc:
        print(f"Diagnostic session failed to launch: {exc}", file=sys.stderr)
        # Keep the partial directory useful: snapshots + journal notes still land.
        _evidence._write_diagnostics_snapshot(after_path, when="after")
        _evidence._collect_journal_log(journal_user_path, since=journal_since, cmd=journal_user_cmd)
        _evidence._collect_journal_log(journal_kernel_path, since=journal_since, cmd=journal_kernel_cmd)
        print(f"Diagnostic session directory: {session_dir}")
        return 2

    # Snapshot after exit so support can diff before/after.
    _evidence._write_diagnostics_snapshot(after_path, when="after")

    # Best-effort journal collection. Failures only write a note and must not
    # change the reported KeyRGB child exit status.
    _evidence._collect_journal_log(journal_user_path, since=journal_since, cmd=journal_user_cmd)
    _evidence._collect_journal_log(journal_kernel_path, since=journal_since, cmd=journal_kernel_cmd)

    print(f"KeyRGB diagnostic session finished (child exit {exit_code}).")
    print(f"Diagnostic session directory: {session_dir}")
    return exit_code


def add_diagnostic_session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--diagnostic-session",
        action="store_true",
        help="Run a full KeyRGB diagnostic session (logs, snapshots, journal).",
    )
    parser.add_argument(
        "--diagnostic-output-dir",
        metavar="DIR",
        default=None,
        help="Override the diagnostic-session output root (default: ~/.cache/keyrgb/diagnostic-sessions).",
    )
    parser.add_argument(
        "--diagnostic-mode",
        choices=RUNTIME_LOG_MODES,
        default="full",
        help="Debug intensity for the session (default: full).",
    )
    parser.add_argument(
        "--runtime-log-launcher",
        choices=RUNTIME_LAUNCHERS,
        default=None,
        help="Override the auto-selected launcher (source when in a checkout, else installed).",
    )


def diagnostic_session_from_cli(argv: Sequence[str], *, prog: str = "keyrgb") -> int | None:
    """Handle ``--diagnostic-session`` arguments, or return ``None`` for a normal launch."""

    session_option_present = any(
        arg == "--diagnostic-session" or arg.startswith("--diagnostic-session=") for arg in argv
    )
    if not session_option_present:
        return None

    parser = argparse.ArgumentParser(prog=prog, description="Run a KeyRGB diagnostic session.")
    add_diagnostic_session_arguments(parser)
    args = parser.parse_args(list(argv))
    return run_diagnostic_session(
        mode=str(args.diagnostic_mode),
        launcher=args.runtime_log_launcher,
        output_dir_root=Path(args.diagnostic_output_dir) if args.diagnostic_output_dir else None,
    )


def diagnostic_session_main(argv: Sequence[str] | None = None) -> None:
    """Console entrypoint for ``keyrgb-diagnostic-launch`` (always runs a session)."""

    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="keyrgb-diagnostic-launch",
        description="Run a full KeyRGB diagnostic session and print its output directory.",
    )
    add_diagnostic_session_arguments(parser)
    args = parser.parse_args(list(argv))
    exit_code = run_diagnostic_session(
        mode=str(args.diagnostic_mode),
        launcher=args.runtime_log_launcher,
        output_dir_root=Path(args.diagnostic_output_dir) if args.diagnostic_output_dir else None,
    )
    raise SystemExit(exit_code)


__all__ = [
    "RUNTIME_LAUNCHERS",
    "RUNTIME_LOG_MODES",
    "RUNTIME_LOG_NAME",
    "RuntimeLogCaptureError",
    "add_diagnostic_session_arguments",
    "diagnostic_session_from_cli",
    "diagnostic_session_main",
    "run_diagnostic_session",
]
