from __future__ import annotations

import json
import textwrap
from pathlib import Path

import buildpython.steps.file_size_analysis.step as step_size
from buildpython.steps.file_size_analysis.scanning import scan_middleman_candidate, scan_unreferenced_file_candidates


def _write_python_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _write_minimal_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(  # noqa: FLY002 - explicit generated fixture lines are easier to review
            [
                "[project]",
                'name = "demo"',
                'version = "0.0.1"',
                "[project.scripts]",
                'demo = "keyrgb.app:main"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_scan_middleman_candidate_flags_non_init_reexport_module(tmp_path) -> None:
    module_path = tmp_path / "keyrgb" / "middleman.py"
    _write_python_file(
        module_path,
        '''
        """Middle-man module."""

        from __future__ import annotations

        from keyrgb.impl import exported_name

        __all__ = ["exported_name"]
        ''',
    )

    result = scan_middleman_candidate(module_path)

    assert result is not None
    assert result["import_statements"] == 2
    assert result["exports"] == 1
    assert result["exported_names"] == ["exported_name"]


def test_scan_unreferenced_file_candidates_fails_open_without_entrypoints(tmp_path) -> None:
    _write_python_file(tmp_path / "keyrgb" / "dead.py", "VALUE = 1")

    rows = scan_unreferenced_file_candidates(tmp_path, roots=("keyrgb",))

    assert rows == []


def test_file_size_runner_reports_middlemen_and_unreferenced_candidates(tmp_path, monkeypatch) -> None:
    _write_minimal_pyproject(tmp_path)
    _write_python_file(
        tmp_path / "keyrgb" / "app.py",
        """
        from keyrgb.middleman import exported_name
        from keyrgb.used import helper


        def main() -> int:
            return helper() + exported_name()
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "used.py",
        """
        def helper() -> int:
            return 1
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "impl.py",
        """
        def exported_name() -> int:
            return 2
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "middleman.py",
        """
        from keyrgb.impl import exported_name

        __all__ = ["exported_name"]
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "dead.py",
        """
        VALUE = 5
        """,
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()

    assert result.exit_code == 0
    assert "Middle-man modules: 1" in result.stdout
    assert "Unreferenced files: 1" in result.stdout
    assert "keyrgb/middleman.py" in result.stdout
    assert "keyrgb/dead.py" in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert payload["counts"]["middleman_modules"] == 1
    assert payload["counts"]["unreferenced_files"] == 1
    assert payload["middleman_modules"][0]["path"] == "keyrgb/middleman.py"
    assert payload["middleman_modules"][0]["inbound_imports"] == 1
    assert payload["unreferenced_files"][0]["path"] == "keyrgb/dead.py"
    assert payload["unreferenced_files"][0]["reason"].startswith("Not reachable from configured entrypoints")

    markdown = (tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.md").read_text(encoding="utf-8")
    assert "## Middle-man modules" in markdown
    assert "## Unreferenced file candidates" in markdown


def test_unreferenced_scan_treats_reachable_python_m_launches_as_roots(tmp_path, monkeypatch) -> None:
    _write_minimal_pyproject(tmp_path)
    _write_python_file(
        tmp_path / "keyrgb" / "app.py",
        """
        from keyrgb.launcher import launch_support


        def main() -> None:
            launch_support()
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "launcher.py",
        """
        import subprocess
        import sys


        def launch_support() -> None:
            subprocess.Popen([sys.executable, "-m", "keyrgb.support"])
        """,
    )
    _write_python_file(
        tmp_path / "keyrgb" / "support.py",
        """
        VALUE = 1
        """,
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()
    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert payload["counts"]["unreferenced_files"] == 0
    assert payload["unreferenced_files"] == []
