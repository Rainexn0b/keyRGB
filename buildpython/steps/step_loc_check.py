from __future__ import annotations

from pathlib import Path

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .reports import write_csv, write_json, write_md


THRESHOLD_LINES = 400


def _iter_py_files() -> list[Path]:
    root = repo_root()

    paths: list[Path] = []
    for folder in [root / "src", root / "buildpython"]:
        if not folder.exists():
            continue
        for p in folder.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            paths.append(p)

    return paths


def loc_over_400_runner() -> RunResult:
    root = repo_root()
    files = _iter_py_files()

    hits: list[tuple[int, str]] = []
    for p in files:
        try:
            line_count = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            continue

        if line_count >= THRESHOLD_LINES:
            hits.append((line_count, str(p.relative_to(root))))

    hits.sort(reverse=True)

    stdout_lines: list[str] = []
    stdout_lines.append("LOC check")
    stdout_lines.append("")
    stdout_lines.append(f"Threshold: >= {THRESHOLD_LINES} lines")

    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "loc-check.json"
    report_csv = report_dir / "loc-check.csv"
    report_md = report_dir / "loc-check.md"

    if not hits:
        stdout_lines.append("No files exceed the threshold.")

        write_json(report_json, {"threshold": THRESHOLD_LINES, "files": []})
        write_csv(report_csv, ["lines", "path"], [])
        write_md(report_md, ["# LOC check", "", f"Threshold: >= {THRESHOLD_LINES} lines", "", "No files exceed the threshold."])

        return RunResult(
            command_str="(internal) loc check",
            stdout="\n".join(stdout_lines) + "\n",
            stderr="",
            exit_code=0,
        )

    stdout_lines.append(f"Files >= {THRESHOLD_LINES} LOC: {len(hits)}")
    stdout_lines.append("")
    stdout_lines.append("Largest files:")
    for line_count, rel in hits[:80]:
        stdout_lines.append(f"  {line_count:4d}  {rel}")

    files_json: list[dict[str, object]] = [{"lines": lc, "path": rel} for lc, rel in hits]

    data = {
        "threshold": THRESHOLD_LINES,
        "count": len(hits),
        "files": files_json,
    }

    write_json(report_json, data)
    write_csv(report_csv, ["lines", "path"], [[str(lc), rel] for lc, rel in hits])

    md_lines: list[str] = [
        "# LOC check",
        "",
        f"Threshold: >= {THRESHOLD_LINES} lines",
        "",
        f"Count: {len(hits)}",
        "",
        "| Lines | Path |",
        "|---:|---|",
    ]
    for lc, rel in hits[:200]:
        md_lines.append(f"| {lc} | {rel} |")
    write_md(report_md, md_lines)

    # Informational by default; do not fail.
    return RunResult(
        command_str="(internal) loc check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=0,
    )
