from __future__ import annotations

import json

from buildpython.steps import step_dead_code
from buildpython.utils.subproc import RunResult


def test_parse_findings_extracts_confidence_and_scope() -> None:
    stdout = "\n".join(  # noqa: FLY002 - multi-line fixture payload is clearer as an explicit list
        [
            "keyrgb/core/example.py:10: unused variable 'x' (100% confidence)",
            "keyrgb/gui/example.py:12: unused import 'y' (90% confidence)",
            "noise line that should be ignored",
        ]
    )

    findings = step_dead_code._parse_findings(stdout)

    assert len(findings) == 2
    assert findings[0]["path"] == "keyrgb/core/example.py"
    assert findings[0]["line"] == 10
    assert findings[0]["confidence"] == 100
    assert findings[0]["scope"] == "keyrgb/core"
    assert findings[1]["scope"] == "keyrgb/gui"


def test_dead_code_runner_treats_unused_variables_as_informational(monkeypatch, tmp_path) -> None:
    fake_stdout = "\n".join(  # noqa: FLY002 - multi-line fixture payload is clearer as an explicit list
        [
            "keyrgb/tray/icon.py:7: unused variable 'outline' (100% confidence)",
            "keyrgb/gui/example.py:12: unused variable 'tag_or_id' (90% confidence)",
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
    assert "Actionable findings: 0" in result.stdout
    assert "keyrgb/tray: 1" in result.stdout
    assert "keyrgb/gui: 1" in result.stdout

    report_dir = tmp_path / "buildlog" / "keyrgb"
    payload = json.loads((report_dir / "dead-code-vulture.json").read_text(encoding="utf-8"))
    assert payload["count"] == 2
    assert payload["actionable_count"] == 0
    assert payload["counts_by_scope"]["keyrgb/gui"] == 1
    assert payload["counts_by_scope"]["keyrgb/tray"] == 1
    assert (report_dir / "dead-code-vulture.md").exists()
    assert (report_dir / "dead-code-vulture.txt").exists()


def test_dead_code_runner_fails_on_unused_runtime_functions(monkeypatch, tmp_path) -> None:
    fake_stdout = "keyrgb/core/example.py:4: unused function 'legacy_helper' (100% confidence)\n"

    monkeypatch.setattr(step_dead_code, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_dead_code, "buildlog_dir", lambda: tmp_path / "buildlog" / "keyrgb")
    monkeypatch.setattr(
        step_dead_code,
        "run",
        lambda *_args, **_kwargs: RunResult(
            command_str="vulture",
            stdout=fake_stdout,
            stderr="",
            exit_code=3,
        ),
    )

    result = step_dead_code.dead_code_runner()

    assert result.exit_code == 1
    assert "Actionable findings: 1" in result.stdout
    assert "legacy_helper" in result.stdout
