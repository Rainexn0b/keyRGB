from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .loc_check_constants import (
    DEFAULT_LOC_BUCKETS,
    DEFAULT_THRESHOLD_LINES,
    LOC_BUCKET_LABELS,
    LOC_BUCKET_ORDER,
    LOC_SCAN_ROOTS,
    loc_bucket,
    loc_scope,
    threshold_descriptions,
    threshold_map,
)
from .reports import write_csv, write_json, write_md


def _iter_py_files() -> list[Path]:
    root = repo_root()

    paths: list[Path] = []
    for root_name in LOC_SCAN_ROOTS:
        folder = root / root_name
        if not folder.exists():
            continue
        for p in folder.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            paths.append(p)

    return paths


def _empty_bucket_counts() -> dict[str, int]:
    counts = {key: 0 for key in LOC_BUCKET_ORDER}
    counts["total"] = 0
    return counts


def _bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = _empty_bucket_counts()
    for item in rows:
        bucket = item.get("bucket")
        if not isinstance(bucket, str):
            continue
        key = bucket.lower()
        if key in counts:
            counts[key] += 1
            counts["total"] += 1
    return counts


def _bucket_counts_by_scope(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts_by_scope = {
        "default": _empty_bucket_counts(),
        "tests": _empty_bucket_counts(),
    }

    for item in rows:
        scope = item.get("scope")
        bucket = item.get("bucket")
        if not isinstance(scope, str) or scope not in counts_by_scope or not isinstance(bucket, str):
            continue
        key = bucket.lower()
        if key in counts_by_scope[scope]:
            counts_by_scope[scope][key] += 1
            counts_by_scope[scope]["total"] += 1

    return counts_by_scope


def _bucket_summary_line(counts: dict[str, int]) -> str | None:
    parts: list[str] = []
    for key in LOC_BUCKET_ORDER:
        current = counts.get(key, 0)
        if current:
            parts.append(f"{LOC_BUCKET_LABELS[key]}={current}")
    if not parts:
        return None
    return "Buckets: " + " | ".join(parts)


def _stdout_label(item: dict[str, Any]) -> str:
    bucket = str(item.get("bucket", ""))
    if item.get("scope") == "tests":
        return f"[TEST {bucket}]"
    return f"[{bucket}]"


def _markdown_lines(*, thresholds: dict[str, str], rows: list[dict[str, Any]], counts: dict[str, int]) -> list[str]:
    md_lines: list[str] = [
        "# LOC check",
        "",
        "## Thresholds",
        "",
        f"- Default file ranges: {thresholds['default']}",
        f"- Test-file ranges: {thresholds['tests']}",
        "",
        "## Bucket counts",
        "",
        "| Bucket | Count |",
        "|---|---:|",
    ]

    for bucket in DEFAULT_LOC_BUCKETS:
        md_lines.append(f"| {bucket.label} | {counts.get(bucket.key, 0)} |")

    md_lines.extend(["", f"Count: {counts.get('total', 0)}", ""])

    if not rows:
        md_lines.append("No files exceed configured LOC thresholds.")
        return md_lines

    md_lines.extend([
        "## Largest files",
        "",
        "| Lines | Bucket | Scope | Path |",
        "|---:|---|---|---|",
    ])
    for item in rows[:200]:
        md_lines.append(
            f"| {int(item['lines'])} | {item['bucket']} | {item['scope']} | {item['path']} |"
        )
    return md_lines


def loc_check_runner() -> RunResult:
    root = repo_root()
    files = _iter_py_files()
    thresholds = threshold_descriptions()

    hits: list[dict[str, Any]] = []
    for p in files:
        try:
            line_count = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue

        rel_path = p.relative_to(root)
        bucket = loc_bucket(line_count, rel_path=rel_path)
        if bucket is None:
            continue
        hits.append(
            {
                "lines": line_count,
                "path": str(rel_path),
                "bucket": bucket,
                "scope": loc_scope(rel_path),
            }
        )

    hits.sort(key=lambda item: (int(item["lines"]), str(item["path"])), reverse=True)
    counts = _bucket_counts(hits)
    counts_by_scope = _bucket_counts_by_scope(hits)

    stdout_lines: list[str] = []
    stdout_lines.append("LOC check")
    stdout_lines.append("")
    stdout_lines.append(f"Default ranges: {thresholds['default']}")
    stdout_lines.append(f"Test-file ranges: {thresholds['tests']}")

    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "loc-check.json"
    report_csv = report_dir / "loc-check.csv"
    report_md = report_dir / "loc-check.md"

    data = {
        "threshold": DEFAULT_THRESHOLD_LINES,
        "thresholds": threshold_map(),
        "scan_roots": list(LOC_SCAN_ROOTS),
        "count": len(hits),
        "counts": counts,
        "counts_by_scope": counts_by_scope,
        "files": hits,
    }

    if not hits:
        stdout_lines.append("")
        stdout_lines.append("No files exceed configured LOC thresholds.")

        write_json(report_json, data)
        write_csv(report_csv, ["lines", "bucket", "scope", "path"], [])
        write_md(report_md, _markdown_lines(thresholds=thresholds, rows=hits, counts=counts))

        return RunResult(
            command_str="(internal) loc check",
            stdout="\n".join(stdout_lines) + "\n",
            stderr="",
            exit_code=0,
        )

    stdout_lines.append("")
    stdout_lines.append(f"Files above configured ranges: {len(hits)}")
    bucket_summary = _bucket_summary_line(counts)
    if bucket_summary is not None:
        stdout_lines.append(bucket_summary)
    stdout_lines.append("")
    stdout_lines.append("Largest files:")
    for item in hits[:80]:
        stdout_lines.append(f"  {_stdout_label(item):<16} {int(item['lines']):4d}  {item['path']}")

    write_json(report_json, data)
    write_csv(
        report_csv,
        ["lines", "bucket", "scope", "path"],
        [[str(item["lines"]), str(item["bucket"]), str(item["scope"]), str(item["path"])] for item in hits],
    )
    write_md(report_md, _markdown_lines(thresholds=thresholds, rows=hits, counts=counts))

    # Informational by default; do not fail.
    return RunResult(
        command_str="(internal) loc check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=0,
    )


# Transitional alias for older internal call sites.
loc_over_400_runner = loc_check_runner
