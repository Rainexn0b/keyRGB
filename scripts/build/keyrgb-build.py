#!/usr/bin/env python3
"""KeyRGB build runner (Python).

This borrows the *patterns* from the JS build system in `scripts/build/`:
- Step-based execution
- Profiles (ci/quick/full)
- Standard, machine-parsable log files

It intentionally stays lightweight and only runs checks that make sense here.

Usage:
  python3 scripts/build/keyrgb-build.py --profile=ci
  python3 scripts/build/keyrgb-build.py --run-steps=1,2
  python3 scripts/build/keyrgb-build.py --run-steps=compileall,pytest
  python3 scripts/build/keyrgb-build.py --list-profiles
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDLOG_DIR = REPO_ROOT / "buildlog" / "keyrgb"


@dataclass(frozen=True)
class Step:
    number: int
    name: str
    description: str
    command: list[str]
    log_file: Path


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_log(step: Step, stdout: str, stderr: str, exit_code: int, duration_s: float) -> None:
    BUILDLOG_DIR.mkdir(parents=True, exist_ok=True)

    command_str = " ".join(shlex.quote(p) for p in step.command)
    content = (
        f"=== {step.name} - {_iso_now()} ===\n"
        f"Command: {command_str}\n"
        f"Duration: ({duration_s:.1f}s)\n"
        f"Exit Code: {exit_code}\n\n"
        f"=== STDOUT ===\n{stdout if stdout.strip() else '(no stdout)'}\n\n"
        f"=== STDERR ===\n{stderr if stderr.strip() else '(no stderr)'}\n\n"
        f"=== END ===\n"
    )
    step.log_file.parent.mkdir(parents=True, exist_ok=True)
    step.log_file.write_text(content, encoding="utf-8")


def _run_step(step: Step, verbose: bool) -> int:
    start = time.time()
    proc = subprocess.run(
        step.command,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env={
            **os.environ,
            # Ensure hardware tests stay opt-in
            "KEYRGB_HW_TESTS": os.environ.get("KEYRGB_HW_TESTS", "0"),
        },
    )
    duration = time.time() - start

    _write_log(step, proc.stdout, proc.stderr, proc.returncode, duration)

    status = "OK" if proc.returncode == 0 else "FAIL"
    print(f"[{step.number}] {step.name}: {status} ({duration:.1f}s)")

    if verbose or proc.returncode != 0:
        if proc.stdout.strip():
            print(proc.stdout.rstrip())
        if proc.stderr.strip():
            print(proc.stderr.rstrip(), file=sys.stderr)

    return proc.returncode


def _steps() -> list[Step]:
    return [
        Step(
            number=1,
            name="Compile",
            description="Compile all Python sources (syntax check)",
            command=[sys.executable, "-m", "compileall", "-q", "src"],
            log_file=BUILDLOG_DIR / "step-01-compile.log",
        ),
        Step(
            number=2,
            name="Pytest",
            description="Run unit tests (hardware tests opt-in)",
            # Override addopts so local runs aren't forced to emit coverage.
            command=[sys.executable, "-m", "pytest", "-q", "-o", "addopts="],
            log_file=BUILDLOG_DIR / "step-02-pytest.log",
        ),
    ]


_BUILD_PROFILES: dict[str, dict[str, object]] = {
    "ci": {
        "description": "CI checks (compile + pytest)",
        "include": ["Compile", "Pytest"],
    },
    "quick": {
        "description": "Quick checks (compile + pytest)",
        "include": ["Compile", "Pytest"],
    },
    "full": {
        "description": "Full local checks (compile + pytest)",
        "include": ["Compile", "Pytest"],
    },
}


def _list_profiles() -> None:
    print("Available profiles:")
    for name, data in sorted(_BUILD_PROFILES.items()):
        print(f"  {name:<8} - {data['description']}")


def _parse_step_selector(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(" ", ",").split(",") if p.strip()]
    return parts


def _select_steps(all_steps: list[Step], run_steps: list[str] | None, skip_steps: list[str] | None, profile: str | None) -> list[Step]:
    by_number = {str(s.number): s for s in all_steps}
    by_name = {s.name.lower(): s for s in all_steps}

    selected: list[Step]

    if run_steps is not None:
        selected = []
        for token in run_steps:
            if token in by_number:
                selected.append(by_number[token])
                continue
            step = by_name.get(token.lower())
            if step is not None:
                selected.append(step)
                continue
            raise SystemExit(f"Unknown step selector: {token!r}")
    elif profile is not None:
        prof = _BUILD_PROFILES.get(profile)
        if prof is None:
            raise SystemExit(f"Unknown profile: {profile!r}")
        include_names = {str(n).lower() for n in prof["include"]}  # type: ignore[index]
        selected = [s for s in all_steps if s.name.lower() in include_names]
    else:
        selected = all_steps

    if skip_steps:
        skip_set = {t.lower() for t in skip_steps}
        selected = [s for s in selected if str(s.number) not in skip_set and s.name.lower() not in skip_set]

    # Deduplicate while preserving order
    seen: set[int] = set()
    unique: list[Step] = []
    for s in selected:
        if s.number in seen:
            continue
        seen.add(s.number)
        unique.append(s)

    return unique


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--profile", choices=sorted(_BUILD_PROFILES.keys()), help="Run a predefined profile")
    parser.add_argument("--list-profiles", action="store_true", help="List profiles and exit")
    parser.add_argument("--run-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--skip-steps", help="Comma/space-separated list of step numbers or names")
    parser.add_argument("--verbose", action="store_true", help="Print stdout/stderr for steps")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.list_profiles:
        _list_profiles()
        return 0

    all_steps = _steps()
    run_steps = _parse_step_selector(args.run_steps)
    skip_steps = _parse_step_selector(args.skip_steps)

    selected = _select_steps(all_steps, run_steps, skip_steps, args.profile)
    if not selected:
        print("No steps selected.")
        return 1

    print(f"KeyRGB build runner (logs: {BUILDLOG_DIR})")

    for step in selected:
        rc = _run_step(step, verbose=args.verbose)
        if rc != 0:
            print(f"Stopped on failure in step {step.number}: {step.name}")
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
