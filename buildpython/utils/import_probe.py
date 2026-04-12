from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .subproc import RunResult, python_exe, run


_IMPORT_PROBE_PROGRAM = """from __future__ import annotations
import importlib
import sys

importlib.import_module(sys.argv[1])
"""


def _last_nonempty_line(text: str) -> str:
    for raw_line in reversed(str(text or "").splitlines()):
        line = raw_line.strip()
        if line:
            return line
    return ""


def _split_error_line(line: str, *, exit_code: int) -> tuple[str, str]:
    if not line:
        return "ImportError", f"probe exited with status {int(exit_code)}"

    exc_type, separator, message = line.partition(": ")
    if separator:
        return exc_type or "ImportError", message

    return line, ""


@dataclass(frozen=True)
class ImportProbeResult:
    module: str
    command_str: str
    stdout: str
    stderr: str
    exit_code: int

    @property
    def ok(self) -> bool:
        return int(self.exit_code) == 0

    @property
    def error_line(self) -> str:
        return _last_nonempty_line(self.stderr)

    @property
    def error_type(self) -> str:
        error_type, _message = _split_error_line(self.error_line, exit_code=self.exit_code)
        return error_type

    @property
    def error_message(self) -> str:
        _error_type, message = _split_error_line(self.error_line, exit_code=self.exit_code)
        return message

    @property
    def failure_detail(self) -> str:
        message = self.error_message
        if not message:
            return self.error_type
        return f"{self.error_type}: {message}"


def probe_module_import(module: str, *, cwd: Path) -> ImportProbeResult:
    result: RunResult = run(
        [python_exe(), "-c", _IMPORT_PROBE_PROGRAM, str(module)],
        cwd=str(cwd),
    )
    return ImportProbeResult(
        module=str(module),
        command_str=result.command_str,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
    )