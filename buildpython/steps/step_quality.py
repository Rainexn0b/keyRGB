from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .reports import write_csv, write_json, write_md


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


_COMMENTED_CODE_RE = re.compile(
    r"^\s*#\s*(def |class |import |from |if |elif |else:|for |while |try:|except |with |return |raise )"
)


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
    for p in [root / "keyrgb", root / "keyrgb-tuxedo"]:
        if p.exists() and p.is_file():
            files.append(p)

    return files


def _scan_one_file(
    *,
    file: Path,
    root: Path,
    counts: Counter[str],
    marker_hits: list[str],
    commented_code_hits: list[str],
    max_marker_hits: int = 200,
    max_commented_hits: int = 200,
) -> None:
    try:
        text = file.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return

    rel = file.relative_to(root)
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in _MARKERS:
            if m not in line:
                continue
            counts[m] += 1
            if len(marker_hits) < max_marker_hits:
                marker_hits.append(f"{rel}:{idx}: {line.strip()}")

        if _COMMENTED_CODE_RE.match(line) and len(commented_code_hits) < max_commented_hits:
            commented_code_hits.append(f"{rel}:{idx}: {line.strip()}")


def _scan_source_files(files: list[Path], *, root: Path) -> tuple[Counter[str], list[str], list[str]]:
    counts: Counter[str] = Counter()
    marker_hits: list[str] = []
    commented_code_hits: list[str] = []
    for file in files:
        _scan_one_file(
            file=file,
            root=root,
            counts=counts,
            marker_hits=marker_hits,
            commented_code_hits=commented_code_hits,
        )
    return counts, marker_hits, commented_code_hits


def _find_ref_files(*, root: Path) -> list[str]:
    ref_files: list[str] = []
    for ext in _REF_EXTS:
        for p in root.rglob(f"*{ext}"):
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            ref_files.append(str(p.relative_to(root)))
    return ref_files


def _build_stdout_lines(
    *,
    counts: Counter[str],
    marker_hits: list[str],
    commented_code_hits: list[str],
    ref_files: list[str],
) -> list[str]:
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
        for path_str in sorted(ref_files)[:200]:
            stdout_lines.append(f"  {path_str}")

    if commented_code_hits:
        stdout_lines.append("")
        stdout_lines.append("Commented-out code (sample):")
        stdout_lines.extend(f"  {h}" for h in commented_code_hits[:40])

    if marker_hits:
        stdout_lines.append("")
        stdout_lines.append("Sample hits:")
        stdout_lines.extend(f"  {h}" for h in marker_hits[:80])

    return stdout_lines


def _write_reports(
    *,
    root: Path,
    counts: Counter[str],
    marker_hits: list[str],
    commented_code_hits: list[str],
    ref_files: list[str],
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "code-markers.json"
    report_csv = report_dir / "code-markers.csv"
    report_md = report_dir / "code-markers.md"

    data = {
        "markers": _MARKERS,
        "marker_counts": {k: int(counts.get(k, 0)) for k in _MARKERS},
        "refactoring_extensions": _REF_EXTS,
        "refactoring_files": sorted(ref_files),
        "commented_out_code_samples": commented_code_hits[:200],
        "marker_samples": marker_hits[:200],
    }

    write_json(report_json, data)
    write_csv(
        report_csv,
        ["type", "path", "line", "text"],
        [
            [
                "MARKER",
                h.split(":", 2)[0],
                h.split(":", 2)[1],
                h.split(":", 2)[2].lstrip(),
            ]
            for h in marker_hits[:200]
            if h.count(":") >= 2
        ]
        + [
            [
                "COMMENTED_CODE",
                h.split(":", 2)[0],
                h.split(":", 2)[1],
                h.split(":", 2)[2].lstrip(),
            ]
            for h in commented_code_hits[:200]
            if h.count(":") >= 2
        ],
    )

    md_lines: list[str] = [
        "# Code markers",
        "",
        "## Counts",
    ]
    if any(counts.values()):
        for k in _MARKERS:
            md_lines.append(f"- {k}: {counts.get(k, 0)}")
    else:
        md_lines.append("- No markers found")

    if ref_files:
        md_lines.extend(["", "## Refactoring/backup files", ""])
        for path_str in sorted(ref_files)[:200]:
            md_lines.append(f"- {path_str}")

    if commented_code_hits:
        md_lines.extend(["", "## Commented-out code (sample)", ""])
        for h in commented_code_hits[:80]:
            md_lines.append(f"- {h}")

    if marker_hits:
        md_lines.extend(["", "## Marker hits (sample)", ""])
        for h in marker_hits[:80]:
            md_lines.append(f"- {h}")

    write_md(report_md, md_lines)


def code_markers_runner() -> RunResult:
    root = repo_root()
    files = _iter_source_files()
    counts, marker_hits, commented_code_hits = _scan_source_files(files, root=root)
    ref_files = _find_ref_files(root=root)
    stdout_lines = _build_stdout_lines(
        counts=counts,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )
    _write_reports(
        root=root,
        counts=counts,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )

    # Never fail the build on this step by default; treat as informational.
    return RunResult(
        command_str="(internal) code marker scan",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=0,
    )
