from __future__ import annotations

import json
from pathlib import Path

import buildpython.steps.step_loc_check as step_loc_check

from buildpython.core.debt_index import build_debt_index
from buildpython.core.summary_support.debt_terminal import build_terminal_loc_check_highlight


def _write_python_file(path: Path, *, total_lines: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"value_{index} = {index}" for index in range(total_lines)) + "\n", encoding="utf-8")


def test_loc_check_runner_uses_bucketed_thresholds_and_relaxed_test_limits(tmp_path, monkeypatch) -> None:
    _write_python_file(tmp_path / "src" / "monitor.py", total_lines=360)
    _write_python_file(tmp_path / "buildpython" / "refactor.py", total_lines=420)
    _write_python_file(tmp_path / "src" / "critical.py", total_lines=500)
    _write_python_file(tmp_path / "src" / "severe.py", total_lines=560)

    _write_python_file(tmp_path / "tests" / "test_monitor.py", total_lines=420)
    _write_python_file(tmp_path / "tests" / "test_refactor.py", total_lines=470)
    _write_python_file(tmp_path / "tests" / "test_critical.py", total_lines=520)
    _write_python_file(tmp_path / "tests" / "test_severe.py", total_lines=620)

    _write_python_file(tmp_path / "src" / "ignored.py", total_lines=349)
    _write_python_file(tmp_path / "tests" / "test_ignored.py", total_lines=399)

    monkeypatch.setattr(step_loc_check, "repo_root", lambda: tmp_path)

    result = step_loc_check.loc_check_runner()

    assert result.exit_code == 0
    assert "Monitor=2 | Refactor=2 | Critical=2 | Severe=2" in result.stdout
    assert "Files above configured ranges: 8" in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "loc-check.json").read_text(encoding="utf-8"))

    assert payload["threshold"] == 350
    assert payload["thresholds"]["default"]["monitor"] == {"min": 350, "max": 399}
    assert payload["thresholds"]["default"]["severe"] == {"min": 550}
    assert payload["thresholds"]["tests"]["critical"] == {"min": 500, "max": 600}
    assert payload["counts"] == {
        "monitor": 2,
        "refactor": 2,
        "critical": 2,
        "severe": 2,
        "total": 8,
    }
    assert payload["counts_by_scope"]["default"] == {
        "monitor": 1,
        "refactor": 1,
        "critical": 1,
        "severe": 1,
        "total": 4,
    }
    assert payload["counts_by_scope"]["tests"] == {
        "monitor": 1,
        "refactor": 1,
        "critical": 1,
        "severe": 1,
        "total": 4,
    }
    assert payload["files"][0]["path"] == "tests/test_severe.py"
    assert payload["files"][0]["scope"] == "tests"
    assert payload["files"][0]["bucket"] == "SEVERE"

    markdown = (tmp_path / "buildlog" / "keyrgb" / "loc-check.md").read_text(encoding="utf-8")
    assert "Default file ranges: monitor=350-399, refactor=400-449, critical=450-549, severe=550+" in markdown
    assert "Test-file ranges: monitor=400-449, refactor=450-499, critical=500-600, severe=601+" in markdown
    assert "| Lines | Bucket | Scope | Path |" in markdown


def test_loc_check_runner_omits_zero_count_buckets_in_stdout(tmp_path, monkeypatch) -> None:
    _write_python_file(tmp_path / "src" / "severe_only.py", total_lines=560)

    monkeypatch.setattr(step_loc_check, "repo_root", lambda: tmp_path)

    result = step_loc_check.loc_check_runner()

    assert result.exit_code == 0
    assert "Severe=1" in result.stdout
    assert "Monitor=" not in result.stdout
    assert "Refactor=" not in result.stdout
    assert "Critical=" not in result.stdout


def test_loc_check_runner_writes_empty_report_when_no_files_exceed_thresholds(tmp_path, monkeypatch) -> None:
    _write_python_file(tmp_path / "src" / "small.py", total_lines=349)
    _write_python_file(tmp_path / "tests" / "test_small.py", total_lines=399)

    monkeypatch.setattr(step_loc_check, "repo_root", lambda: tmp_path)

    result = step_loc_check.loc_check_runner()

    assert result.exit_code == 0
    assert "No files exceed configured LOC thresholds." in result.stdout
    assert "Buckets:" not in result.stdout

    payload = json.loads((tmp_path / "buildlog" / "keyrgb" / "loc-check.json").read_text(encoding="utf-8"))
    assert payload["counts"] == {
        "monitor": 0,
        "refactor": 0,
        "critical": 0,
        "severe": 0,
        "total": 0,
    }
    assert payload["files"] == []


def test_debt_index_preserves_richer_loc_check_payload(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "loc-check.json").write_text(
        json.dumps(
            {
                "threshold": 350,
                "thresholds": {
                    "default": {"monitor": {"min": 350, "max": 399}},
                    "tests": {"critical": {"min": 500, "max": 600}},
                },
                "count": 1,
                "counts": {"monitor": 0, "refactor": 0, "critical": 0, "severe": 1, "total": 1},
                "counts_by_scope": {
                    "default": {"monitor": 0, "refactor": 0, "critical": 0, "severe": 0, "total": 0},
                    "tests": {"monitor": 0, "refactor": 0, "critical": 0, "severe": 1, "total": 1},
                },
                "files": [{"path": "tests/test_big.py", "lines": 620, "bucket": "SEVERE", "scope": "tests"}],
            }
        ),
        encoding="utf-8",
    )

    payload = build_debt_index(buildlog_dir)

    assert payload["sections"]["loc_check"]["thresholds"]["tests"]["critical"] == {"min": 500, "max": 600}
    assert payload["sections"]["loc_check"]["counts"]["severe"] == 1
    assert payload["sections"]["loc_check"]["counts_by_scope"]["tests"]["severe"] == 1


def test_terminal_loc_check_highlight_summarizes_buckets_and_top_file(tmp_path) -> None:
    buildlog_dir = tmp_path / "buildlog"
    buildlog_dir.mkdir()
    (buildlog_dir / "loc-check.json").write_text(
        json.dumps(
            {
                "count": 3,
                "counts": {"monitor": 1, "refactor": 0, "critical": 1, "severe": 1, "total": 3},
                "counts_by_scope": {
                    "default": {"monitor": 1, "refactor": 0, "critical": 1, "severe": 0, "total": 2},
                    "tests": {"monitor": 0, "refactor": 0, "critical": 0, "severe": 1, "total": 1},
                },
                "files": [{"path": "tests/test_big.py", "lines": 620, "bucket": "SEVERE", "scope": "tests"}],
            }
        ),
        encoding="utf-8",
    )

    lines = build_terminal_loc_check_highlight(buildlog_dir)

    assert any("monitor 1" in line and "critical 1" in line and "severe 1" in line and "tests 1" in line for line in lines)
    assert any("Top LOC" in line and "tests/test_big.py" in line and "SEVERE" in line for line in lines)