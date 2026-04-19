from __future__ import annotations

import json
from pathlib import Path
import textwrap

import buildpython.steps.file_size_analysis.step as step_size
from buildpython.steps.file_size_analysis.scanning import scan_middleman_candidate, scan_unreferenced_file_candidates

from buildpython.core.debt_index import build_debt_index, write_debt_index
from buildpython.core.summary import BuildSummary, write_summary
from buildpython.core.summary_support.debt_terminal import build_terminal_filesize_highlight


def _write_python_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def _write_minimal_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "demo"',
                'version = "0.0.1"',
                "[project.scripts]",
                'demo = "src.app:main"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_scan_middleman_candidate_flags_non_init_reexport_module(tmp_path) -> None:
    module_path = tmp_path / "src" / "middleman.py"
    _write_python_file(
        module_path,
        '''
        """Middle-man module."""

        from __future__ import annotations

        from src.impl import exported_name

        __all__ = ["exported_name"]
        ''',
    )

    result = scan_middleman_candidate(module_path)

    assert result is not None
    assert result["import_statements"] == 2
    assert result["exports"] == 1
    assert result["exported_names"] == ["exported_name"]


def test_scan_unreferenced_file_candidates_fails_open_without_entrypoints(tmp_path) -> None:
    _write_python_file(tmp_path / "src" / "dead.py", "VALUE = 1")

    rows = scan_unreferenced_file_candidates(tmp_path, roots=("src",))

    assert rows == []


def test_file_size_runner_reports_middlemen_and_unreferenced_candidates(tmp_path, monkeypatch) -> None:
    _write_minimal_pyproject(tmp_path)
    _write_python_file(
        tmp_path / "src" / "app.py",
        '''
        from src.middleman import exported_name
        from src.used import helper


        def main() -> int:
            return helper() + exported_name()
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "used.py",
        '''
        def helper() -> int:
            return 1
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "impl.py",
        '''
        def exported_name() -> int:
            return 2
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "middleman.py",
        '''
        from src.impl import exported_name

        __all__ = ["exported_name"]
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "dead.py",
        '''
        VALUE = 5
        ''',
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()

    assert result.exit_code == 0
    assert "Middle-man modules: 1" in result.stdout
    assert "Unreferenced files: 1" in result.stdout
    assert "src/middleman.py" in result.stdout
    assert "src/dead.py" in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert payload["counts"]["middleman_modules"] == 1
    assert payload["counts"]["unreferenced_files"] == 1
    assert payload["middleman_modules"][0]["path"] == "src/middleman.py"
    assert payload["middleman_modules"][0]["inbound_imports"] == 1
    assert payload["unreferenced_files"][0]["path"] == "src/dead.py"
    assert payload["unreferenced_files"][0]["reason"].startswith("Not reachable from configured entrypoints")

    markdown = (tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.md").read_text(encoding="utf-8")
    assert "## Middle-man modules" in markdown
    assert "## Unreferenced file candidates" in markdown


def test_unreferenced_scan_treats_reachable_python_m_launches_as_roots(tmp_path, monkeypatch) -> None:
    _write_minimal_pyproject(tmp_path)
    _write_python_file(
        tmp_path / "src" / "app.py",
        '''
        from src.launcher import launch_support


        def main() -> None:
            launch_support()
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "launcher.py",
        '''
        import subprocess
        import sys


        def launch_support() -> None:
            subprocess.Popen([sys.executable, "-m", "src.support"])
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "support.py",
        '''
        VALUE = 1
        ''',
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()
    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert payload["counts"]["unreferenced_files"] == 0
    assert payload["unreferenced_files"] == []


def test_file_size_runner_suppresses_middleman_and_unreferenced_for_waived_files(tmp_path, monkeypatch) -> None:
    _write_minimal_pyproject(tmp_path)
    _write_python_file(
        tmp_path / "src" / "app.py",
        '''
        from src.impl import exported_name
        from src.used import helper


        def main() -> int:
            return helper() + exported_name()
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "used.py",
        '''
        def helper() -> int:
            return 1
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "impl.py",
        '''
        def exported_name() -> int:
            return 2
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "middleman.py",
        '''
        # @quality-exception file-size-analysis: intentional export facade module
        from src.impl import exported_name

        __all__ = ["exported_name"]
        ''',
    )
    _write_python_file(
        tmp_path / "src" / "dead.py",
        '''
        # @quality-exception file-size-analysis: temporary standalone migration helper
        VALUE = 5
        ''',
    )

    monkeypatch.setattr(step_size, "repo_root", lambda: tmp_path)

    result = step_size.file_size_runner()
    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "file-size-analysis.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert payload["counts"]["middleman_modules"] == 0
    assert payload["counts"]["unreferenced_files"] == 0
    assert payload["counts"]["waived_files"] == 2
    assert payload["middleman_modules"] == []
    assert payload["unreferenced_files"] == []
    assert {item["path"] for item in payload["waivers"]["files"]} == {"src/dead.py", "src/middleman.py"}
    assert "[waived] src/middleman.py" in result.stdout
    assert "[waived] src/dead.py" in result.stdout


def test_file_size_debt_summaries_include_middleman_and_deadfile_candidates(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "file-size-analysis.json").write_text(
        json.dumps(
            {
                "counts": {
                    "file_lines": {"refactor": 0, "critical": 0, "severe": 0, "extreme": 0, "total": 0},
                    "import_block_lines": {"warning": 0, "critical": 0, "severe": 0, "total": 0},
                    "flat_directories": 0,
                    "delegation_candidates": 1,
                    "middleman_modules": 1,
                    "unreferenced_files": 1,
                },
                "files": [],
                "import_blocks": [],
                "flat_directories": [],
                "delegation_candidates": [{"path": "src/delegation.py", "score": 12}],
                "middleman_modules": [{"path": "src/middleman.py", "exports": 3, "inbound_imports": 2}],
                "unreferenced_files": [{"path": "src/dead.py", "lines": 12, "inbound_imports": 0}],
            }
        ),
        encoding="utf-8",
    )

    payload = build_debt_index(buildlog_dir)

    assert payload["sections"]["file_size"]["middleman_modules"][0]["path"] == "src/middleman.py"
    assert payload["sections"]["file_size"]["unreferenced_files"][0]["path"] == "src/dead.py"

    write_debt_index(buildlog_dir)
    write_summary(
        buildlog_dir,
        BuildSummary(
            passed=True,
            health_score=100,
            total_duration_s=0.1,
            steps=[],
        ),
    )

    debt_markdown = (buildlog_dir / "debt-index.md").read_text(encoding="utf-8")
    summary_markdown = (buildlog_dir / "build-summary.md").read_text(encoding="utf-8")
    lines = build_terminal_filesize_highlight(buildlog_dir)

    assert "Middle-man modules: 1" in debt_markdown
    assert "Unreferenced file candidates: 1" in debt_markdown
    assert "Top middle-man module: src/middleman.py (exports=3)" in debt_markdown
    assert "Top dead-file candidate: src/dead.py (12 lines)" in debt_markdown

    assert "Middle-man modules: 1" in summary_markdown
    assert "Unreferenced file candidates: 1" in summary_markdown
    assert "Top middle-man module: src/middleman.py (exports=3)" in summary_markdown
    assert "Top dead-file candidate: src/dead.py (12 lines)" in summary_markdown

    assert any("middlemen 1" in line for line in lines)
    assert any("dead-files 1" in line for line in lines)
    assert any("Top middleman" in line and "src/middleman.py" in line for line in lines)
    assert any("Top dead-file" in line and "src/dead.py" in line for line in lines)