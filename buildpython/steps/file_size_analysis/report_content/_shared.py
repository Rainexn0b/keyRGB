from __future__ import annotations

from typing import Any


def file_counts(file_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "refactor": sum(1 for item in file_rows if item["bucket"] == "REFACTOR"),
        "critical": sum(1 for item in file_rows if item["bucket"] == "CRITICAL"),
        "severe": sum(1 for item in file_rows if item["bucket"] == "SEVERE"),
        "extreme": sum(1 for item in file_rows if item["bucket"] == "EXTREME"),
        "total": len(file_rows),
    }


def import_counts(import_rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "warning": sum(1 for item in import_rows if item["level"] == "WARNING"),
        "critical": sum(1 for item in import_rows if item["level"] == "CRITICAL"),
        "severe": sum(1 for item in import_rows if item["level"] == "SEVERE"),
        "total": len(import_rows),
    }


def delegation_count(delegation_rows: list[dict[str, Any]]) -> int:
    return len(delegation_rows)


def middleman_count(middleman_rows: list[dict[str, Any]]) -> int:
    return len(middleman_rows)


def unreferenced_count(unreferenced_rows: list[dict[str, Any]]) -> int:
    return len(unreferenced_rows)