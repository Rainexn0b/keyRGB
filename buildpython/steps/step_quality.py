from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
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

_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")


@dataclass(frozen=True)
class MarkerBaseline:
    counts: dict[str, int]
    gated_markers: set[str]


def _load_marker_baseline(root: Path) -> MarkerBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return MarkerBaseline(counts={}, gated_markers=set())

    section = payload.get("code_markers", {})
    counts_raw = section.get("marker_counts", {})
    counts = {
        str(marker): int(value)
        for marker, value in counts_raw.items()
        if isinstance(value, int | float)
    }
    gated_markers = {
        str(marker)
        for marker in section.get("gated_markers", [])
        if isinstance(marker, str)
    }
    return MarkerBaseline(counts=counts, gated_markers=gated_markers)


def _marker_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    delta = current - baseline
    return f"{delta:+d}"


def _marker_regressions(counts: Counter[str], baseline: MarkerBaseline) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for marker in sorted(baseline.gated_markers):
        current = counts.get(marker, 0)
        expected = baseline.counts.get(marker, 0)
        if current > expected:
            regressions.append((marker, current, expected))
    return regressions


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
    counts_by_file_marker: Counter[tuple[str, str]],
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
    rel_str = str(rel)
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in _MARKERS:
            if m not in line:
                continue
            counts[m] += 1
            counts_by_file_marker[(rel_str, m)] += 1
            if len(marker_hits) < max_marker_hits:
                marker_hits.append(f"{rel}:{idx}: {line.strip()}")

        if _COMMENTED_CODE_RE.match(line) and len(commented_code_hits) < max_commented_hits:
            commented_code_hits.append(f"{rel}:{idx}: {line.strip()}")


def _scan_source_files(files: list[Path], *, root: Path) -> tuple[Counter[str], Counter[tuple[str, str]], list[str], list[str]]:
    counts: Counter[str] = Counter()
    counts_by_file_marker: Counter[tuple[str, str]] = Counter()
    marker_hits: list[str] = []
    commented_code_hits: list[str] = []
    for file in files:
        _scan_one_file(
            file=file,
            root=root,
            counts=counts,
            counts_by_file_marker=counts_by_file_marker,
            marker_hits=marker_hits,
            commented_code_hits=commented_code_hits,
        )
    return counts, counts_by_file_marker, marker_hits, commented_code_hits


def _top_marker_files(counts_by_file_marker: Counter[tuple[str, str]]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {marker: Counter() for marker in _MARKERS}
    for (path_str, marker), count in counts_by_file_marker.items():
        grouped.setdefault(marker, Counter())[path_str] += count
    return {
        marker: grouped[marker].most_common(10)
        for marker in _MARKERS
        if grouped.get(marker)
    }


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
    baseline: MarkerBaseline,
    top_marker_files: dict[str, list[tuple[str, int]]],
    marker_hits: list[str],
    commented_code_hits: list[str],
    ref_files: list[str],
) -> list[str]:
    stdout_lines: list[str] = []
    regressions = _marker_regressions(counts, baseline)
    stdout_lines.append("Code marker scan summary")
    stdout_lines.append("")

    if counts:
        stdout_lines.append("Marker counts:")
        for k in _MARKERS:
            if counts.get(k, 0):
                baseline_count = baseline.counts.get(k)
                baseline_text = "-" if baseline_count is None else str(baseline_count)
                delta = _marker_delta(counts[k], baseline_count)
                stdout_lines.append(f"  {k}: {counts[k]}  baseline={baseline_text} delta={delta}")
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
    regressions = _marker_regressions(counts, baseline)

    data = {
        "markers": _MARKERS,
        "marker_counts": {k: int(counts.get(k, 0)) for k in _MARKERS},
        "baseline": {
            "marker_counts": baseline.counts,
            "gated_markers": sorted(baseline.gated_markers),
            "regressions": [
                {"marker": marker, "current": current, "baseline": expected}
                for marker, current, expected in regressions
            ],
        },
        "top_marker_files": {
            marker: [
                {"path": path_str, "count": count}
                for path_str, count in hotspots
            ]
            for marker, hotspots in top_marker_files.items()
        },
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
            baseline_count = baseline.counts.get(k)
            baseline_text = "-" if baseline_count is None else str(baseline_count)
            delta = _marker_delta(counts.get(k, 0), baseline_count)
            md_lines.append(f"- {k}: {counts.get(k, 0)} (baseline {baseline_text}, delta {delta})")
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
        for h in commented_code_hits[:80]:
            md_lines.append(f"- {h}")

    if marker_hits:
        md_lines.extend(["", "## Marker hits (sample)", ""])
        for h in marker_hits[:80]:
            md_lines.append(f"- {h}")

    write_md(report_md, md_lines)


def code_markers_runner() -> RunResult:
    root = repo_root()
    baseline = _load_marker_baseline(root)
    files = _iter_source_files()
    counts, counts_by_file_marker, marker_hits, commented_code_hits = _scan_source_files(files, root=root)
    top_marker_files = _top_marker_files(counts_by_file_marker)
    ref_files = _find_ref_files(root=root)
    stdout_lines = _build_stdout_lines(
        counts=counts,
        baseline=baseline,
        top_marker_files=top_marker_files,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )
    _write_reports(
        root=root,
        counts=counts,
        baseline=baseline,
        top_marker_files=top_marker_files,
        marker_hits=marker_hits,
        commented_code_hits=commented_code_hits,
        ref_files=ref_files,
    )

    exit_code = 1 if _marker_regressions(counts, baseline) else 0

    return RunResult(
        command_str="(internal) code marker scan",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
