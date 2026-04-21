from __future__ import annotations

import json

from buildpython.utils.subproc import RunResult

import buildpython.steps.step_dead_code as step_dead_code


def test_parse_findings_extracts_confidence_and_scope() -> None:
    stdout = "\n".join(
        [
            "src/core/example.py:10: unused variable 'x' (100% confidence)",
            "src/gui/example.py:12: unused import 'y' (90% confidence)",
            "noise line that should be ignored",
        ]
    )

    findings = step_dead_code._parse_findings(stdout)

    assert len(findings) == 2
    assert findings[0]["path"] == "src/core/example.py"
    assert findings[0]["line"] == 10
    assert findings[0]["confidence"] == 100
    assert findings[0]["scope"] == "src/core"
    assert findings[1]["scope"] == "src/gui"


def test_dead_code_runner_treats_vulture_findings_as_informational(monkeypatch, tmp_path) -> None:
    fake_stdout = "\n".join(
        [
            "src/tray/icon.py:7: unused variable 'outline' (100% confidence)",
            "buildpython/core/cli.py:8: unused import 'x' (80% confidence)",
        ]
    )

    monkeypatch.setattr(step_dead_code, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_dead_code, "buildlog_dir", lambda: tmp_path / "buildlog" / "keyrgb")

    def fake_run(args, *, cwd, env_overrides):
        assert cwd == str(tmp_path)
        assert env_overrides == {"KEYRGB_HW_TESTS": "0"}
        assert "vulture" in args
        return RunResult(
            command_str="python -m vulture src buildpython tests --min-confidence 80",
            stdout=fake_stdout,
            stderr="",
            exit_code=3,
        )

    monkeypatch.setattr(step_dead_code, "run", fake_run)

    result = step_dead_code.dead_code_runner()

    assert result.exit_code == 0
    assert "Dead code scan (vulture)" in result.stdout
    assert "Findings: 2" in result.stdout
    assert "src/tray: 1" in result.stdout
    assert "buildpython: 1" in result.stdout

    report_dir = tmp_path / "buildlog" / "keyrgb"
    payload = json.loads((report_dir / "dead-code-vulture.json").read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["counts_by_scope"]["buildpython"] == 1
    assert payload["counts_by_scope"]["src/tray"] == 1
    assert (report_dir / "dead-code-vulture.md").exists()
    assert (report_dir / "dead-code-vulture.txt").exists()
