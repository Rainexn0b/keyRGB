from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..reports import write_csv, write_json, write_md
from .baseline import COUNT_CATEGORIES
from .models import ExceptionTransparencyAnnotationInventory, ExceptionTransparencyFinding


def top_files_by_category(findings: list[ExceptionTransparencyFinding]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {}
    for finding in findings:
        grouped.setdefault(finding.category, Counter())[finding.path] += 1
    return {category: counter.most_common(20) for category, counter in grouped.items()}


def build_stdout(
    findings: list[ExceptionTransparencyFinding],
    counts: Counter[str],
    waived_total: int,
    annotation_inventory: ExceptionTransparencyAnnotationInventory,
) -> list[str]:
    lines: list[str] = []
    top_files = top_files_by_category(findings)

    lines.append("Exception Transparency Check")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Counts (active; {waived_total} waived via @quality-exception exception-transparency):")
    for category in COUNT_CATEGORIES:
        current = counts.get(category, 0)
        lines.append(f"  {category:<32} {current:>4}")

    lines.append("")
    lines.append(
        "Valid @quality-exception exception-transparency annotations: "
        f"{annotation_inventory.total}"
    )
    for subtree, count in annotation_inventory.by_subtree[:10]:
        lines.append(f"  {count:>3}  {subtree}")

    for category, title in [
        ("broad_except_unlogged", "Unlogged broad catch hotspots"),
        ("broad_except_logged_no_traceback", "Broad catch hotspots without traceback"),
        ("broad_except_total", "Broad catch hotspots"),
        ("naked_except", "Naked except hotspots"),
    ]:
        hotspots = top_files.get(category, [])
        if not hotspots:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for path, count in hotspots[:10]:
            lines.append(f"  {count:>3}  {path}")

    if findings:
        lines.append("")
        lines.append("Sample findings (first 60):")
        for finding in findings[:60]:
            lines.append(f"  [{finding.category}] {finding.path}:{finding.line}")
            lines.append(f"    {finding.message}")
            if finding.snippet:
                lines.append(f"    > {finding.snippet}")

    return lines


def write_reports(
    root: Path,
    findings: list[ExceptionTransparencyFinding],
    counts: Counter[str],
    waived_total: int,
    annotation_inventory: ExceptionTransparencyAnnotationInventory,
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_dir.mkdir(parents=True, exist_ok=True)

    top_files = top_files_by_category(findings)

    write_json(
        report_dir / "exception-transparency.json",
        {
            "counts": {category: int(counts.get(category, 0)) for category in COUNT_CATEGORIES},
            "waived_total": waived_total,
            "annotation_inventory": {
                "total": annotation_inventory.total,
                "by_subtree": [
                    {"subtree": subtree, "count": count}
                    for subtree, count in annotation_inventory.by_subtree
                ],
            },
            "top_files_by_category": {
                category: [{"path": path, "count": count} for path, count in file_counts]
                for category, file_counts in top_files.items()
            },
            "findings": [
                {
                    "category": finding.category,
                    "path": finding.path,
                    "line": finding.line,
                    "message": finding.message,
                    "snippet": finding.snippet,
                }
                for finding in findings[:500]
            ],
        },
    )

    write_csv(
        report_dir / "exception-transparency.csv",
        ["category", "path", "line", "message", "snippet"],
        [
            [finding.category, finding.path, str(finding.line), finding.message, finding.snippet]
            for finding in findings[:500]
        ],
    )

    md_lines: list[str] = [
        "# Exception Transparency Report",
        "",
        f"Active broad exception counts ({waived_total} handlers waived via `@quality-exception exception-transparency`).",
        "",
        "## Summary",
        "",
        "| Category | Active |",
        "|----------|-------:|",
    ]
    for category in COUNT_CATEGORIES:
        current = counts.get(category, 0)
        md_lines.append(f"| {category} | {current} |")

    md_lines.extend(
        [
            "",
            "## Runtime-Boundary Annotation Inventory",
            "",
            f"- Total valid annotations: {annotation_inventory.total}",
        ]
    )
    if annotation_inventory.by_subtree:
        md_lines.extend(["", "| Subtree | Count |", "|---------|------:|"])
        for subtree, count in annotation_inventory.by_subtree:
            md_lines.append(f"| {subtree} | {count} |")
    else:
        md_lines.extend(["", "No valid annotations found."])

    for category, title in [
        ("broad_except_unlogged", "Unlogged Broad Catch Hotspots"),
        ("broad_except_logged_no_traceback", "Broad Catch Hotspots Without Traceback"),
        ("broad_except_total", "Broad Catch Hotspots"),
        ("naked_except", "Naked Except Hotspots"),
    ]:
        hotspots = top_files.get(category, [])
        if not hotspots:
            continue
        md_lines.extend(["", f"## {title}", "", "| File | Count |", "|------|------:|"])
        for path, count in hotspots[:15]:
            md_lines.append(f"| {path} | {count} |")

    if findings:
        md_lines.extend(["", "## Findings (sample)", ""])
        for finding in findings[:100]:
            md_lines.append(f"### `{finding.category}` at {finding.path}:{finding.line}")
            md_lines.append("")
            md_lines.append(f"**{finding.message}**")
            if finding.snippet:
                md_lines.extend(["```python", finding.snippet, "```"])
            md_lines.append("")

    write_md(report_dir / "exception-transparency.md", md_lines)
