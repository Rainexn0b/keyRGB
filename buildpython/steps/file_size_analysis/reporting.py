from __future__ import annotations

from pathlib import Path
from typing import Any

from ..reports import write_csv, write_json, write_md
from .report_content import build_json_payload, build_markdown_lines, build_stdout_lines
from .report_csv import build_csv_rows


def write_reports(
    *,
    root: Path,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    flat_directories_allowed: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
    middleman_rows: list[dict[str, Any]],
    unreferenced_rows: list[dict[str, Any]],
    waiver_rows: list[dict[str, str]],
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_json = report_dir / "file-size-analysis.json"
    report_csv = report_dir / "file-size-analysis.csv"
    report_md = report_dir / "file-size-analysis.md"

    write_json(
        report_json,
        build_json_payload(
            file_rows=file_rows,
            import_rows=import_rows,
            flat_directories=flat_directories,
            flat_directories_allowed=flat_directories_allowed,
            delegation_rows=delegation_rows,
            middleman_rows=middleman_rows,
            unreferenced_rows=unreferenced_rows,
            waiver_rows=waiver_rows,
        ),
    )

    write_csv(
        report_csv,
        ["section", "primary", "secondary", "level", "path", "details"],
        build_csv_rows(
            file_rows=file_rows,
            import_rows=import_rows,
            flat_directories=flat_directories,
            delegation_rows=delegation_rows,
            middleman_rows=middleman_rows,
            unreferenced_rows=unreferenced_rows,
            waiver_rows=waiver_rows,
        ),
    )

    write_md(
        report_md,
        build_markdown_lines(
            file_rows=file_rows,
            import_rows=import_rows,
            flat_directories=flat_directories,
            flat_directories_allowed=flat_directories_allowed,
            delegation_rows=delegation_rows,
            middleman_rows=middleman_rows,
            unreferenced_rows=unreferenced_rows,
            waiver_rows=waiver_rows,
        ),
    )


__all__ = ["build_stdout_lines", "write_reports"]
