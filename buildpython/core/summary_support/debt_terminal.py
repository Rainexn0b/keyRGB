from __future__ import annotations

from pathlib import Path

from .common import (
    file_size_counts,
    file_size_structure_candidate_counts,
    loc_bucket_parts,
    loc_check_counts,
    read_json_if_exists,
)


def _top_file(top_files: object, category: str) -> tuple[str, object] | None:
    if not isinstance(top_files, dict):
        return None
    hotspots = top_files.get(category, [])
    if not isinstance(hotspots, list) or not hotspots or not isinstance(hotspots[0], dict):
        return None
    path = hotspots[0].get("path")
    count = hotspots[0].get("count")
    return (str(path), count) if isinstance(path, str) else None


def _top_annotation_subtree(annotation_inventory: object) -> tuple[str, object] | None:
    if not isinstance(annotation_inventory, dict):
        return None
    raw_subtrees = annotation_inventory.get("by_subtree", [])
    if not isinstance(raw_subtrees, list) or not raw_subtrees or not isinstance(raw_subtrees[0], dict):
        return None
    subtree = raw_subtrees[0].get("subtree")
    count = raw_subtrees[0].get("count")
    return (str(subtree), count) if isinstance(subtree, str) else None


def build_terminal_hygiene_highlight(buildlog_dir: Path) -> list[str]:
    hygiene = read_json_if_exists(buildlog_dir / "code-hygiene.json")
    if hygiene is None:
        return []

    active = hygiene.get("active_counts", {})
    suppressed = hygiene.get("suppressed_counts", {})
    top_files = hygiene.get("top_files_by_category", {})

    parts: list[str] = []
    for key, label in [
        ("silent_broad_except", "silent"),
        ("logged_broad_except", "logged"),
        ("fallback_broad_except", "fallback"),
        ("cleanup_hotspot", "cleanup"),
        ("forbidden_getattr", "getattr"),
    ]:
        current = active.get(key)
        if not isinstance(current, int):
            continue
        s = suppressed.get(key, 0)
        parts.append(f"{label} {current} ({s})" if isinstance(s, int) and s else f"{label} {current}")

    if not parts:
        return []

    lines: list[str] = ["\U0001f50d  " + "  \u00b7  ".join(parts)]
    for category, label in [
        ("silent_broad_except", "Top silent"),
        ("logged_broad_except", "Top logged"),
        ("fallback_broad_except", "Top fallback"),
        ("cleanup_hotspot", "Top cleanup"),
    ]:
        hit = _top_file(top_files, category)
        if hit:
            lines.append(f"{label + ':':<16}  {hit[0]} ({hit[1]})")

    return lines


def build_terminal_transparency_highlight(buildlog_dir: Path) -> list[str]:
    exception_transparency = read_json_if_exists(buildlog_dir / "exception-transparency.json")
    if exception_transparency is None:
        return []

    counts = exception_transparency.get("counts", {})
    waived_total = exception_transparency.get("waived_total", 0)
    annotation_inventory = exception_transparency.get("annotation_inventory", {})

    parts: list[str] = []
    for key, label in [
        ("broad_except_total", "total"),
        ("broad_except_unlogged", "unlogged"),
        ("broad_except_traceback_logged", "traceback"),
    ]:
        current = counts.get(key)
        if not isinstance(current, int):
            continue
        if key == "broad_except_total" and isinstance(waived_total, int) and waived_total:
            parts.append(f"{label} {current} ({waived_total})")
        else:
            parts.append(f"{label} {current}")

    if isinstance(annotation_inventory, dict):
        annotation_total = annotation_inventory.get("total")
        if isinstance(annotation_total, int):
            parts.append(f"annotated {annotation_total}")

    if not parts:
        return []

    lines: list[str] = ["\U0001f9ea  " + "  \u00b7  ".join(parts)]
    top_files = exception_transparency.get("top_files_by_category", {})
    for category, label in [
        ("broad_except_unlogged", "Top unlogged"),
        ("broad_except_total", "Top broad"),
    ]:
        hit = _top_file(top_files, category)
        if hit:
            lines.append(f"{label + ':':<16}  {hit[0]} ({hit[1]})")

    annotated = _top_annotation_subtree(annotation_inventory)
    if annotated is not None:
        lines.append(f"{'Top annotated:':<16}  {annotated[0]} ({annotated[1]})")

    return lines


def build_terminal_markers_highlight(buildlog_dir: Path) -> list[str]:
    markers = read_json_if_exists(buildlog_dir / "code-markers.json")
    if markers is None:
        return []

    marker_counts = markers.get("marker_counts", {})
    top_marker_files = markers.get("top_marker_files", {})

    parts: list[str] = []
    for marker in ["TODO", "FIXME", "HACK", "NOTE"]:
        current = marker_counts.get(marker)
        if not isinstance(current, int):
            continue
        parts.append(f"{marker} {current}")

    if not parts:
        return []

    lines: list[str] = ["\U0001f4dd  " + "  \u00b7  ".join(parts)]
    if isinstance(top_marker_files, dict):
        for marker in ["HACK", "FIXME", "TODO", "NOTE"]:
            hit = _top_file(top_marker_files, marker)
            if hit:
                lines.append(f"{'Top ' + marker + ':':<16}  {hit[0]} ({hit[1]})")

    return lines


def build_terminal_filesize_highlight(buildlog_dir: Path) -> list[str]:
    file_size = read_json_if_exists(buildlog_dir / "file-size-analysis.json")
    if file_size is None:
        return []

    file_counts, import_counts, flat_directory_count, delegation_candidate_count = file_size_counts(file_size)
    middleman_candidate_count, unreferenced_candidate_count = file_size_structure_candidate_counts(file_size)
    files = file_size.get("files", [])
    import_blocks = file_size.get("import_blocks", [])
    flat_directories = file_size.get("flat_directories", [])
    delegation_candidates = file_size.get("delegation_candidates", [])
    middleman_modules = file_size.get("middleman_modules", [])
    unreferenced_files = file_size.get("unreferenced_files", [])

    fs_parts = [
        f"refactor {file_counts.get('refactor', 0)}",
        f"import-warn {import_counts.get('warning', 0)}",
        f"flat-dirs {flat_directory_count}",
        f"delegations {delegation_candidate_count}",
    ]
    if middleman_candidate_count:
        fs_parts.append(f"middlemen {middleman_candidate_count}")
    if unreferenced_candidate_count:
        fs_parts.append(f"dead-files {unreferenced_candidate_count}")
    lines: list[str] = ["\U0001f4c1  " + "  \u00b7  ".join(fs_parts)]

    if isinstance(files, list) and files and isinstance(files[0], dict):
        lines.append(f"{'Top large:':<16}  {files[0].get('path')} ({files[0].get('lines')})")
    if isinstance(import_blocks, list) and import_blocks and isinstance(import_blocks[0], dict):
        lines.append(f"{'Top import:':<16}  {import_blocks[0].get('path')} ({import_blocks[0].get('lines')})")
    if isinstance(flat_directories, list) and flat_directories and isinstance(flat_directories[0], dict):
        lines.append(
            f"{'Top flat-dir:':<16}  {flat_directories[0].get('path')} "
            f"({flat_directories[0].get('direct_python_files')} files)"
        )
    if isinstance(delegation_candidates, list) and delegation_candidates and isinstance(delegation_candidates[0], dict):
        lines.append(
            f"{'Top delegation:':<16}  {delegation_candidates[0].get('path')} (score={delegation_candidates[0].get('score')})"
        )
    if isinstance(middleman_modules, list) and middleman_modules and isinstance(middleman_modules[0], dict):
        lines.append(
            f"{'Top middleman:':<16}  {middleman_modules[0].get('path')} "
            f"(exports={middleman_modules[0].get('exports')})"
        )
    if isinstance(unreferenced_files, list) and unreferenced_files and isinstance(unreferenced_files[0], dict):
        lines.append(
            f"{'Top dead-file:':<16}  {unreferenced_files[0].get('path')} "
            f"({unreferenced_files[0].get('lines')} lines)"
        )

    return lines


def build_terminal_loc_check_highlight(buildlog_dir: Path) -> list[str]:
    loc_check = read_json_if_exists(buildlog_dir / "loc-check.json")
    if loc_check is None:
        return []

    counts, _default_counts, test_counts = loc_check_counts(loc_check)
    parts = loc_bucket_parts(counts, assignment=False)
    if test_counts.get("total", 0):
        parts.append(f"tests {test_counts['total']}")
    if not parts:
        return []

    lines: list[str] = ["\U0001f4cf  " + "  \u00b7  ".join(parts)]
    files = loc_check.get("files", [])
    if isinstance(files, list) and files and isinstance(files[0], dict):
        path = files[0].get("path")
        line_count = files[0].get("lines")
        bucket = files[0].get("bucket")
        if isinstance(path, str):
            detail = f"{path} ({line_count}"
            if isinstance(bucket, str):
                detail += f", {bucket}"
            detail += ")"
            lines.append(f"{'Top LOC:':<16}  {detail}")

    return lines
