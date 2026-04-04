from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..reports import write_csv, write_json, write_md
from .baseline import MARKERS, REF_EXTS, marker_delta, marker_regressions
from .models import MarkerBaseline


def build_stdout_lines(
    *,
    counts: Counter[str],
    baseline: MarkerBaseline,
    top_marker_files: dict[str, list[tuple[str, int]]],
    marker_hits: list[str],
    commented_code_hits: list[str],
    ref_files: list[str],
) -> list[str]:
    stdout_lines: list[str] = []
    regressions = marker_regressions(counts, baseline)
    stdout_lines.append("Code marker scan summary")
    stdout_lines.append("")

    if counts:
        stdout_lines.append("Marker counts:")
        for marker in MARKERS:
            if counts.get(marker, 0):
                baseline_count = baseline.counts.get(marker)
                baseline_text = "-" if baseline_count is None else str(baseline_count)
                delta = marker_delta(counts[marker], baseline_count)
                stdout_lines.append(f"  {marker}: {counts[marker]}  baseline={baseline_text} delta={delta}")
    else:
        stdout_lines.append("No markers found.")

    if regressions:
        stdout_lines.append("")
        stdout_lines.append("Regression-gated marker increases:")
        for marker, current, expected in regressions:
            stdout_lines.append(f"  {marker}: {current} > baseline {expected}")

    for marker in ["HACK", "FIXME", "TODO"]:
        hotspots = top_marker_files.get(marker, [])
        if not hotspots:
            continue
        stdout_lines.append("")
        stdout_lines.append(f"Top {marker} hotspots:")
        for path_str, count in hotspots[:10]:
            stdout_lines.append(f"  {count:>3}  {path_str}")

    if ref_files:
        stdout_lines.append("")
        stdout_lines.append("Refactoring/backup files detected:")
        for path_str in sorted(ref_files)[:200]:
            stdout_lines.append(f"  {path_str}")

    if commented_code_hits:
        stdout_lines.append("")
        stdout_lines.append("Commented-out code (sample):")
        stdout_lines.extend(f"  {hit}" for hit in commented_code_hits[:40])

    if marker_hits:
        stdout_lines.append("")
        stdout_lines.append("Sample hits:")
        stdout_lines.extend(f"  {hit}" for hit in marker_hits[:80])

    return stdout_lines


def write_reports(
    *,
    root: Path,
    counts: Counter[str],
    baseline: MarkerBaseline,
    top_marker_files: dict[str, list[tuple[str, int]]],
    marker_hits: list[str],
    commented_code_hits: list[str],
    ref_files: list[str],
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "code-markers.json"
    report_csv = report_dir / "code-markers.csv"
    report_md = report_dir / "code-markers.md"
    regressions = marker_regressions(counts, baseline)

    data = {
        "markers": MARKERS,
        "marker_counts": {marker: int(counts.get(marker, 0)) for marker in MARKERS},
        "baseline": {
            "marker_counts": baseline.counts,
            "gated_markers": sorted(baseline.gated_markers),
            "regressions": [
                {"marker": marker, "current": current, "baseline": expected}
                for marker, current, expected in regressions
            ],
        },
        "top_marker_files": {
            marker: [{"path": path_str, "count": count} for path_str, count in hotspots]
            for marker, hotspots in top_marker_files.items()
        },
        "refactoring_extensions": REF_EXTS,
        "refactoring_files": sorted(ref_files),
        "commented_out_code_samples": commented_code_hits[:200],
        "marker_samples": marker_hits[:200],
    }

    write_json(report_json, data)
    write_csv(
        report_csv,
        ["type", "path", "line", "text"],
        [
            ["MARKER", hit.split(":", 2)[0], hit.split(":", 2)[1], hit.split(":", 2)[2].lstrip()]
            for hit in marker_hits[:200]
            if hit.count(":") >= 2
        ]
        + [
            ["COMMENTED_CODE", hit.split(":", 2)[0], hit.split(":", 2)[1], hit.split(":", 2)[2].lstrip()]
            for hit in commented_code_hits[:200]
            if hit.count(":") >= 2
        ],
    )

    md_lines: list[str] = ["# Code markers", "", "## Counts"]
    if any(counts.values()):
        for marker in MARKERS:
            baseline_count = baseline.counts.get(marker)
            baseline_text = "-" if baseline_count is None else str(baseline_count)
            delta = marker_delta(counts.get(marker, 0), baseline_count)
            md_lines.append(f"- {marker}: {counts.get(marker, 0)} (baseline {baseline_text}, delta {delta})")
    else:
        md_lines.append("- No markers found")

    if regressions:
        md_lines.extend(["", "## Regression-Gated Marker Increases", ""])
        md_lines.append("| Marker | Current | Baseline |")
        md_lines.append("|--------|--------:|---------:|")
        for marker, current, expected in regressions:
            md_lines.append(f"| {marker} | {current} | {expected} |")

    for marker in ["HACK", "FIXME", "TODO"]:
        hotspots = top_marker_files.get(marker, [])
        if not hotspots:
            continue
        md_lines.extend(["", f"## Top {marker} hotspots", ""])
        md_lines.append("| File | Count |")
        md_lines.append("|------|------:|")
        for path_str, count in hotspots[:10]:
            md_lines.append(f"| {path_str} | {count} |")

    if ref_files:
        md_lines.extend(["", "## Refactoring/backup files", ""])
        for path_str in sorted(ref_files)[:200]:
            md_lines.append(f"- {path_str}")

    if commented_code_hits:
        md_lines.extend(["", "## Commented-out code (sample)", ""])
        for hit in commented_code_hits[:80]:
            md_lines.append(f"- {hit}")

    if marker_hits:
        md_lines.extend(["", "## Marker hits (sample)", ""])
        for hit in marker_hits[:80]:
            md_lines.append(f"- {hit}")

    write_md(report_md, md_lines)
