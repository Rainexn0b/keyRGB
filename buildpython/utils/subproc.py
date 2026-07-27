from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    command_str: str
    stdout: str
    stderr: str
    exit_code: int


def run(
    args: list[str],
    *,
    cwd: str,
    env_overrides: Mapping[str, str] | None = None,
) -> RunResult:
    command_str = " ".join(shlex.quote(p) for p in args)
    env = {**os.environ, **(env_overrides or {})}

    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    return RunResult(
        command_str=command_str,
        stdout=proc.stdout,
        stderr=proc.stderr,
        exit_code=proc.returncode,
    )


def python_exe() -> str:
    return sys.executable
