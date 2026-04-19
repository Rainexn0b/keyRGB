from __future__ import annotations

from typing import Any


def build_csv_rows(
    *,
    file_rows: list[dict[str, Any]],
    import_rows: list[dict[str, Any]],
    flat_directories: list[dict[str, Any]],
    delegation_rows: list[dict[str, Any]],
    middleman_rows: list[dict[str, Any]],
    unreferenced_rows: list[dict[str, Any]],
    waiver_rows: list[dict[str, str]],
) -> list[list[str]]:
    return [["file", str(item["lines"]), "", str(item["bucket"]), str(item["path"]), ""] for item in file_rows] + [
        [
            "import_block",
            str(item["lines"]),
            str(item["statements"]),
            str(item["level"]),
            str(item["path"]),
            "",
        ]
        for item in import_rows
    ] + [
        [
            "flat_directory",
            str(item["direct_python_files"]),
            str(item["subdirectories"]),
            "STRUCTURE",
            str(item["path"]),
            ", ".join(str(example) for example in item["examples"]),
        ]
        for item in flat_directories
    ] + [
        [
            "delegation_candidate",
            str(item["score"]),
            str(item["import_lines"]),
            "DELEGATION",
            str(item["path"]),
            (
                f"aliases={item['alias_bindings']}, delegates={item['delegating_callables']}, "
                f"callables={item['callables']}"
            ),
        ]
        for item in delegation_rows
    ] + [
        [
            "middleman_module",
            str(item["exports"]),
            str(item["inbound_imports"]),
            "MIDDLEMAN",
            str(item["path"]),
            (
                f"imports={item['import_statements']}, aliases={item['alias_bindings']}, "
                f"exports={','.join(str(name) for name in item['exported_names'][:5])}"
            ),
        ]
        for item in middleman_rows
    ] + [
        [
            "unreferenced_file",
            str(item["lines"]),
            str(item["inbound_imports"]),
            "UNREFERENCED",
            str(item["path"]),
            str(item["reason"]),
        ]
        for item in unreferenced_rows
    ] + [
        [
            "quality_exception_waiver",
            "",
            "",
            "WAIVED",
            str(item["path"]),
            str(item["reason"]),
        ]
        for item in waiver_rows
    ]