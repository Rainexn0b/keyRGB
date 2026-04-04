from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..reports import write_csv, write_json, write_md
from .models import HygieneIssue


def _build_stdout(
    issues: list[HygieneIssue],
    active_counts: Counter[str],
    suppressed_counts: Counter[str],
    *,
    category_thresholds: dict[str, int],
) -> list[str]:
    lines: list[str] = []
    top_files_by_category = _top_files_by_category(issues)

    lines.append("Code Hygiene Check")
    lines.append("=" * 40)
    lines.append("")

    lines.append("Issue counts by category (active / suppressed / threshold):")
    for category, threshold in category_thresholds.items():
        active = active_counts.get(category, 0)
        suppressed = suppressed_counts.get(category, 0)
        status = "FAIL" if active > threshold else "OK"
        supp_text = f"  suppressed={suppressed}" if suppressed else ""
        lines.append(f"  {category:<25} active={active:>4} / {threshold:<4}{supp_text} [{status}]")

    active_total = sum(active_counts.values())
    suppressed_total = sum(suppressed_counts.values())
    lines.append("")
    lines.append(f"Total: {active_total} active, {suppressed_total} suppressed")

    for category, title in [
        ("silent_broad_except", "Silent exception debt hotspots"),
        ("logged_broad_except", "Logged exception debt hotspots"),
        ("fallback_broad_except", "Fallback exception debt hotspots"),
        ("cleanup_hotspot", "Cleanup debt hotspots"),
        ("forbidden_api", "Forbidden API hotspots"),
    ]:
        hotspots = top_files_by_category.get(category, [])
        if not hotspots:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for path, count in hotspots[:10]:
            lines.append(f"  {count:>3}  {path}")

    if issues:
        lines.append("")
        lines.append("Sample issues (first 50):")
        for issue in issues[:50]:
            loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
            suppressed_tag = "  [suppressed]" if issue.suppressed else ""
            lines.append(f"  [{issue.category}] {loc}{suppressed_tag}")
            lines.append(f"    {issue.message}")
            if issue.snippet:
                lines.append(f"    > {issue.snippet[:80]}")

    return lines


def _top_files_by_category(issues: list[HygieneIssue]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {}
    for issue in issues:
        if not issue.suppressed:
            counter = grouped.setdefault(issue.category, Counter())
            counter[issue.path] += 1

    return {category: counter.most_common(20) for category, counter in grouped.items()}


def _write_reports(
    root: Path,
    issues: list[HygieneIssue],
    active_counts: Counter[str],
    suppressed_counts: Counter[str],
    *,
    category_thresholds: dict[str, int],
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_json = report_dir / "code-hygiene.json"
    report_csv = report_dir / "code-hygiene.csv"
    report_md = report_dir / "code-hygiene.md"
    top_files_by_category = _top_files_by_category(issues)

    data = {
        "thresholds": dict(category_thresholds),
        "active_counts": {cat: int(active_counts.get(cat, 0)) for cat in category_thresholds},
        "suppressed_counts": {cat: int(suppressed_counts.get(cat, 0)) for cat in category_thresholds},
        "total_active": sum(active_counts.values()),
        "total_suppressed": sum(suppressed_counts.values()),
        "top_files_by_category": {
            category: [{"path": path, "count": count} for path, count in file_counts]
            for category, file_counts in top_files_by_category.items()
        },
        "issues": [
            {
                "category": issue.category,
                "path": issue.path,
                "line": issue.line,
                "message": issue.message,
                "snippet": issue.snippet,
                "suppressed": issue.suppressed,
            }
            for issue in issues[:500]
        ],
    }
    write_json(report_json, data)

    write_csv(
        report_csv,
        ["category", "path", "line", "message", "snippet", "suppressed"],
        [
            [issue.category, issue.path, str(issue.line), issue.message, issue.snippet, str(issue.suppressed)]
            for issue in issues[:500]
        ],
    )

    md_lines: list[str] = [
        "# Code Hygiene Report",
        "",
        "## Summary",
        "",
        "| Category | Active | Suppressed | Threshold | Status |",
        "|----------|-------:|-----------:|----------:|--------|",
    ]
    for category, threshold in category_thresholds.items():
        active = active_counts.get(category, 0)
        suppressed = suppressed_counts.get(category, 0)
        status = "❌ FAIL" if active > threshold else "✅ OK"
        md_lines.append(f"| {category} | {active} | {suppressed} | {threshold} | {status} |")

    md_lines.extend(
        ["", f"**Active:** {sum(active_counts.values())}  **Suppressed:** {sum(suppressed_counts.values())}", ""]
    )

    for category, title in [
        ("silent_broad_except", "Silent Exception Debt Hotspots"),
        ("logged_broad_except", "Logged Exception Debt Hotspots"),
        ("fallback_broad_except", "Fallback Exception Debt Hotspots"),
        ("cleanup_hotspot", "Cleanup Debt Hotspots"),
        ("forbidden_api", "Forbidden API Hotspots"),
        ("resource_leak", "Resource Leak Hotspots"),
    ]:
        hotspots = top_files_by_category.get(category, [])
        if not hotspots:
            continue
        md_lines.extend([f"## {title}", ""])
        md_lines.append("| File | Count |")
        md_lines.append("|------|------:|")
        for path, count in hotspots[:15]:
            md_lines.append(f"| {path} | {count} |")
        md_lines.append("")

    active_issues = [i for i in issues if not i.suppressed]
    if active_issues:
        md_lines.extend(["## Active Issues (sample)", ""])
        for issue in active_issues[:100]:
            loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
            md_lines.append(f"### `{issue.category}` at {loc}")
            md_lines.append("")
            md_lines.append(f"**{issue.message}**")
            if issue.snippet:
                md_lines.append("```python")
                md_lines.append(issue.snippet)
                md_lines.append("```")
            md_lines.append("")

    write_md(report_md, md_lines)
