from __future__ import annotations

import json

import pytest

from buildpython.steps import step_architecture_validation
from tests.buildpython._architecture_validation_unit_support import (
    _assignment_rule_payload,
    _forbid_all_call_rule_payload,
    _forbidden_under_lock_payload,
    _lock_order_payload,
    _poller_engine_call_rule_payload,
)


def test_architecture_validation_runner_serializes_lock_orders_and_findings(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_lock_order_payload()), encoding="utf-8")
    (tmp_path / "keyrgb").mkdir()
    (tmp_path / "keyrgb/runtime.py").write_text(
        "with engine.kb_lock:\n    with self._start_lock:\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    report = json.loads((tmp_path / "buildlog/architecture-validation.json").read_text(encoding="utf-8"))
    assert report["rules"][0]["lock_orders"][0]["locks"][0] == {
        "name": "_start_lock",
        "aliases": ["self._start_lock", "engine._start_lock", "tray.engine._start_lock"],
    }
    assert report["findings"][0]["lock"] == "_start_lock"
    assert report["findings"][0]["outer_locks"] == ["engine.kb_lock"]


def test_architecture_validation_runner_serializes_assignment_rules_and_findings(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_assignment_rule_payload()), encoding="utf-8")
    (tmp_path / "keyrgb").mkdir()
    (tmp_path / "keyrgb/runtime.py").write_text("desired.exact = 1\n", encoding="utf-8")
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    report = json.loads((tmp_path / "buildlog/architecture-validation.json").read_text(encoding="utf-8"))
    assert report["rules"][0]["assignments"] == [
        {
            "targets": ["desired.exact", "named_expr"],
            "target_suffixes": [".forbidden", ".compat"],
            "message": "direct state assignment",
        }
    ]
    assert report["findings"][0]["regex"] == "assignment:desired.exact"
    assert "direct state assignment" in (tmp_path / "buildlog/architecture-validation.csv").read_text(encoding="utf-8")
    assert "no-state-assignments" in (tmp_path / "buildlog/architecture-validation.md").read_text(encoding="utf-8")
    assert "direct state assignment" in result.stdout


def test_architecture_validation_runner_returns_failed_result_for_malformed_keyword_exemption(
    monkeypatch, tmp_path
) -> None:
    payload = _poller_engine_call_rule_payload()
    payload["rules"][0]["calls"][1]["skip_if_keywords"] = ["not a dict"]
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    assert "invalid keyword exemption" in result.stderr


def test_architecture_runner_serializes_keyword_exemptions(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_poller_engine_call_rule_payload()), encoding="utf-8")
    (tmp_path / "keyrgb/tray/pollers").mkdir(parents=True)
    (tmp_path / "keyrgb/tray/pollers/example.py").write_text(
        "tray.engine.set_brightness(5, apply_to_hardware=False)\n", encoding="utf-8"
    )
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 0
    report = json.loads((tmp_path / "buildlog/architecture-validation.json").read_text(encoding="utf-8"))
    call_report = report["rules"][0]["calls"][1]
    assert call_report["required_locks"] == []
    assert call_report["skip_if_keywords"] == [{"name": "apply_to_hardware", "equals": False}]
    assert report["findings"] == []


def test_architecture_validation_runner_serializes_forbidden_under_lock_rules_and_findings(
    monkeypatch, tmp_path
) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbidden_under_lock_payload()), encoding="utf-8")
    (tmp_path / "keyrgb").mkdir()
    (tmp_path / "keyrgb/runtime.py").write_text(
        "with self.kb_lock:\n    subprocess.run([])\n",
        encoding="utf-8",
    )
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    report = json.loads((tmp_path / "buildlog/architecture-validation.json").read_text(encoding="utf-8"))
    forbidden = report["rules"][0]["forbidden_under_locks"]
    assert forbidden[2]["match_any_receiver"] is True
    assert forbidden[3]["required_locks"] == [
        "kb_lock",
        "self.kb_lock",
        "engine.kb_lock",
        "tray.engine.kb_lock",
    ]
    assert report["findings"][0]["regex"] == "forbidden-under-lock:subprocess.run"
    assert report["findings"][0]["lock"] == "self.kb_lock"


def test_architecture_validation_runner_serializes_forbid_all_call_rules_and_findings(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbid_all_call_rule_payload()), encoding="utf-8")
    (tmp_path / "keyrgb").mkdir()
    (tmp_path / "keyrgb/runtime.py").write_text("engine.kb.set_color((1, 2, 3), brightness=5)\n", encoding="utf-8")
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        config_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    report = json.loads((tmp_path / "buildlog/architecture-validation.json").read_text(encoding="utf-8"))
    assert report["rules"][0]["calls"][0]["allowed_files"] == []
    assert report["rules"][0]["calls"][0]["forbid_all"] is True
    assert report["findings"][0]["regex"] == "call:engine.kb.set_color"
    assert "engine.kb.set_color" in (tmp_path / "buildlog/architecture-validation.csv").read_text(encoding="utf-8")
    assert "unapproved primary lighting owner" in (tmp_path / "buildlog/architecture-validation.md").read_text(
        encoding="utf-8"
    )


def test_architecture_validation_runner_returns_run_result_for_recoverable_rule_errors(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    def fake_load(_config_path):
        raise ValueError("bad rules")

    monkeypatch.setattr(step_architecture_validation, "load_architecture_rules", fake_load)

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    assert "Failed to load rules or scan the repo." in result.stdout
    assert result.stderr == "bad rules\n"


def test_architecture_validation_runner_propagates_unexpected_scan_bug(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")
    monkeypatch.setattr(step_architecture_validation, "load_architecture_rules", lambda _config_path: [])

    def fake_scan(_root, _rules):
        raise AssertionError("unexpected scan bug")

    monkeypatch.setattr(step_architecture_validation, "scan_architecture", fake_scan)

    with pytest.raises(AssertionError, match="unexpected scan bug"):
        step_architecture_validation.architecture_validation_runner()
