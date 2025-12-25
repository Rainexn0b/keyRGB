from __future__ import annotations

from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult


WARN_LINES = 350
CRIT_LINES = 600
SEVERE_LINES = 900


def _iter_py_files() -> list[Path]:
    root = repo_root()
    src = root / "src"
    if not src.exists():
        return []

    files: list[Path] = []
    for p in src.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        files.append(p)
    return files


def file_size_runner() -> RunResult:
    root = repo_root()
    files = _iter_py_files()

    rows: list[tuple[int, str]] = []
    for p in files:
        try:
            line_count = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            continue
        if line_count >= WARN_LINES:
            rows.append((line_count, str(p.relative_to(root))))

    rows.sort(reverse=True)

    stdout_lines: list[str] = []
    stdout_lines.append("File size analysis")
    stdout_lines.append("")
    stdout_lines.append(f"Thresholds: warn>={WARN_LINES}, critical>={CRIT_LINES}, severe>={SEVERE_LINES}")

    if not rows:
        stdout_lines.append("No large files detected.")
        return RunResult(
            command_str="(internal) file size analysis",
            stdout="\n".join(stdout_lines) + "\n",
            stderr="",
            exit_code=0,
        )

    severe = [r for r in rows if r[0] >= SEVERE_LINES]
    critical = [r for r in rows if CRIT_LINES <= r[0] < SEVERE_LINES]
    warn = [r for r in rows if WARN_LINES <= r[0] < CRIT_LINES]

    stdout_lines.append(f"Severe: {len(severe)} | Critical: {len(critical)} | Warning: {len(warn)}")
    stdout_lines.append("")
    stdout_lines.append("Largest files:")
    for line_count, rel in rows[:50]:
        level = "SEVERE" if line_count >= SEVERE_LINES else "CRITICAL" if line_count >= CRIT_LINES else "WARN"
        stdout_lines.append(f"  [{level}] {line_count:4d}  {rel}")

    # Informational by default; do not fail.
    return RunResult(
        command_str="(internal) file size analysis",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=0,
    )
