from __future__ import annotations

from pathlib import Path

import pytest

from buildpython.utils.project_metadata import ProjectMetadataError, read_project_dependencies


def _write_pyproject(path: Path, text: str) -> Path:
    pyproject_path = path / "pyproject.toml"
    pyproject_path.write_text(text, encoding="utf-8")
    return pyproject_path


def test_read_project_dependencies_preserves_order_and_strips_whitespace(tmp_path: Path) -> None:
    pyproject_path = _write_pyproject(
        tmp_path,
        '[project]\nname = "keyrgb"\ndependencies = ["  pystray>=0.19.5  ", "Pillow>=12.2.0"]\n',
    )

    assert read_project_dependencies(pyproject_path) == ("pystray>=0.19.5", "Pillow>=12.2.0")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[project]\nname = "keyrgb"\n', "at least one dependency"),
        ("[project]\ndependencies = []\n", "at least one dependency"),
        ("[project]\ndependencies = [1]\n", "must be a string"),
        ('[project]\ndependencies = ["  "]\n', "must not be blank"),
        ("[tool.ruff]\nline-length = 120\n", r"missing a \[project\] table"),
    ],
)
def test_read_project_dependencies_rejects_invalid_shapes(tmp_path: Path, text: str, message: str) -> None:
    pyproject_path = _write_pyproject(tmp_path, text)

    with pytest.raises(ProjectMetadataError, match=message):
        read_project_dependencies(pyproject_path)


def test_read_project_dependencies_reports_missing_or_malformed_file(tmp_path: Path) -> None:
    with pytest.raises(ProjectMetadataError, match="cannot read"):
        read_project_dependencies(tmp_path / "missing.toml")

    malformed = _write_pyproject(tmp_path, "[project]\ndependencies = [\n")
    with pytest.raises(ProjectMetadataError, match="cannot parse"):
        read_project_dependencies(malformed)
