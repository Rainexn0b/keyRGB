from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


class ProjectMetadataError(ValueError):
    """Raised when required project metadata cannot be read safely."""


def _toml_parser() -> Any:
    try:
        return importlib.import_module("tomllib")
    except ModuleNotFoundError:
        try:
            return importlib.import_module("tomli")
        except ModuleNotFoundError as exc:
            raise ProjectMetadataError(
                "reading pyproject.toml on Python < 3.11 requires the project dev extras"
            ) from exc


def read_project_dependencies(pyproject_path: Path) -> tuple[str, ...]:
    """Return the non-empty ``[project].dependencies`` sequence."""

    parser = _toml_parser()
    try:
        payload = parser.loads(pyproject_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectMetadataError(f"cannot read {pyproject_path}: {exc}") from exc
    except parser.TOMLDecodeError as exc:
        raise ProjectMetadataError(f"cannot parse {pyproject_path}: {exc}") from exc

    project = payload.get("project")
    if not isinstance(project, dict):
        raise ProjectMetadataError("pyproject.toml is missing a [project] table")

    dependencies = project.get("dependencies")
    if dependencies is None:
        raise ProjectMetadataError("[project].dependencies must declare at least one dependency")
    if not isinstance(dependencies, list):
        raise ProjectMetadataError("[project].dependencies must be a list")

    normalized: list[str] = []
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, str):
            raise ProjectMetadataError(f"[project].dependencies[{index}] must be a string")
        specifier = dependency.strip()
        if not specifier:
            raise ProjectMetadataError(f"[project].dependencies[{index}] must not be blank")
        normalized.append(specifier)

    if not normalized:
        raise ProjectMetadataError("[project].dependencies must declare at least one dependency")
    return tuple(normalized)
