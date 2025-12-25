from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult


_MARKERS = [
    "TODO",
    "FIXME",
    "HACK",
    "NOTE",
    "OPTIMIZE",
    "REVIEW",
]

_REF_EXTS = [
    ".new",
    ".old",
    ".bak",
    ".tmp",
    ".v2",
    ".wip",
    ".ref",
    ".archive",
]


def _iter_source_files() -> list[Path]:
    root = repo_root()
    src = root / "src"
    if not src.exists():
        return []

    files: list[Path] = []
    for p in src.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        files.append(p)

    # Also consider top-level scripts
    for p in [root / "keyrgb", root / "keyrgb-tuxedo", root / "keyrgb-tray.py"]:
        if p.exists() and p.is_file():
            files.append(p)

    return files


def code_markers_runner() -> RunResult:
    files = _iter_source_files()
    counts: Counter[str] = Counter()

    marker_hits: list[str] = []
    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for idx, line in enumerate(text.splitlines(), start=1):
            for m in _MARKERS:
                if m in line:
                    counts[m] += 1
                    # keep output compact; include a few hits
                    if len(marker_hits) < 200:
                        marker_hits.append(f"{file.relative_to(repo_root())}:{idx}: {line.strip()}")

    ref_files: list[str] = []
    root = repo_root()
    for ext in _REF_EXTS:
        for p in root.rglob(f"*{ext}"):
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            ref_files.append(str(p.relative_to(root)))

    stdout_lines: list[str] = []
    stdout_lines.append("Code marker scan summary")
    stdout_lines.append("")

    if counts:
        stdout_lines.append("Marker counts:")
        for k in _MARKERS:
            if counts.get(k, 0):
                stdout_lines.append(f"  {k}: {counts[k]}")
    else:
        stdout_lines.append("No markers found.")

    if ref_files:
        stdout_lines.append("")
        stdout_lines.append("Refactoring/backup files detected:")
        for p in sorted(ref_files)[:200]:
            stdout_lines.append(f"  {p}")

    if marker_hits:
        stdout_lines.append("")
        stdout_lines.append("Sample hits:")
        stdout_lines.extend(f"  {h}" for h in marker_hits[:80])

    # Never fail the build on this step by default; treat as informational.
    return RunResult(
        command_str="(internal) code marker scan",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=0,
    )
