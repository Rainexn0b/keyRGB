from __future__ import annotations

import json
import re

import pytest

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import load_architecture_rules
from tests.buildpython._architecture_validation_unit_support import (
    _assignment_rule_payload,
    _call_rule_payload,
    _forbid_all_call_rule_payload,
    _forbidden_under_lock_payload,
    _poller_engine_call_rule_payload,
)


def test_load_architecture_rules_parses_flags_and_corpus(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "demo-rule",
                        "description": "Demo",
                        "severity": "warning",
                        "corpus": {
                            "include": ["keyrgb/**/*.py"],
                            "exclude": ["tests/**/*.py"],
                        },
                        "patterns": [
                            {
                                "regex": "^import forbidden$",
                                "flags": "mi",
                                "message": "Forbidden import",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)

    assert len(rules) == 1
    assert rules[0].rule_id == "demo-rule"
    assert rules[0].severity == "warning"
    assert rules[0].include_globs == ("keyrgb/**/*.py",)
    assert rules[0].exclude_globs == ("tests/**/*.py",)
    assert rules[0].patterns[0].compiled.flags & re.MULTILINE
    assert rules[0].patterns[0].compiled.flags & re.IGNORECASE
    assert rules[0].imports == ()


def test_load_architecture_rules_parses_import_rules(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "gui-logic-bleed",
                        "description": "GUI logic bleed",
                        "severity": "warning",
                        "corpus": {
                            "include": ["keyrgb/gui/**/*.py"],
                        },
                        "imports": [
                            {
                                "module": "keyrgb.core.backends.registry",
                                "message": "GUI should not import backend selection directly",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)

    assert len(rules) == 1
    assert rules[0].patterns == ()
    assert len(rules[0].imports) == 1
    assert rules[0].imports[0].module == "keyrgb.core.backends.registry"
    assert rules[0].imports[0].message == "GUI should not import backend selection directly"
    assert rules[0].attributes == ()


def test_load_architecture_rules_parses_attribute_rules(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "tray-ui-private-hooks",
                        "description": "Tray UI private hook bleed",
                        "severity": "warning",
                        "corpus": {
                            "include": ["keyrgb/tray/ui/**/*.py"],
                        },
                        "attributes": [
                            {
                                "name": "_update_menu",
                                "message": "Tray UI should not call private runtime menu refresh hooks directly",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)

    assert len(rules) == 1
    assert rules[0].patterns == ()
    assert rules[0].imports == ()
    assert len(rules[0].attributes) == 1
    assert rules[0].attributes[0].name == "_update_menu"
    assert rules[0].attributes[0].message == "Tray UI should not call private runtime menu refresh hooks directly"


def test_load_architecture_rules_parses_assignment_rules(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_assignment_rule_payload()), encoding="utf-8")

    assignment_rules = load_architecture_rules(config_path)[0].assignment_rules

    assert len(assignment_rules) == 1
    assert assignment_rules[0].targets == ("desired.exact", "named_expr")
    assert assignment_rules[0].target_suffixes == (".forbidden", ".compat")
    assert assignment_rules[0].message == "direct state assignment"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["rules"][0].update(assignments={}),
        lambda payload: payload["rules"][0].update(assignments=["not an object"]),
        lambda payload: payload["rules"][0]["assignments"][0].update(targets="desired.exact"),
        lambda payload: payload["rules"][0]["assignments"][0].update(targets=[], target_suffixes=[]),
        lambda payload: payload["rules"][0]["assignments"][0].update(message=""),
        lambda payload: payload["rules"][0]["assignments"][0].update(message=None),
    ],
)
def test_load_architecture_rules_rejects_malformed_assignment_rules(tmp_path, mutate) -> None:
    payload = _assignment_rule_payload()
    mutate(payload)
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="assignment"):
        load_architecture_rules(config_path)


def test_load_architecture_rules_parses_forbidden_under_lock_calls(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbidden_under_lock_payload()), encoding="utf-8")

    forbidden = load_architecture_rules(config_path)[0].forbidden_under_locks

    assert len(forbidden) == 4
    assert forbidden[0].receivers == ("time",)
    assert forbidden[1].receiver_suffixes == (".process",)
    assert forbidden[2].match_any_receiver is True
    assert forbidden[2].methods == ("join", "wait", "communicate")
    assert forbidden[3].methods == ("run", "call", "check_call", "check_output", "Popen")


def test_load_architecture_rules_rejects_malformed_forbidden_under_lock_call(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    payload = _forbidden_under_lock_payload()
    payload["rules"][0]["forbidden_under_locks"][0].pop("required_locks")
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid forbidden-under-lock call entry"):
        load_architecture_rules(config_path)


def test_load_architecture_rules_rejects_malformed_lock_order(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "bad-lock-order",
                        "description": "Bad lock order",
                        "severity": "error",
                        "corpus": {"include": ["keyrgb/**/*.py"]},
                        "lock_orders": [{"locks": [{"name": "kb_lock"}]}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid lock-order entry"):
        load_architecture_rules(config_path)


def test_load_architecture_rules_parses_call_rules_and_runner_serializes_them(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_call_rule_payload()), encoding="utf-8")

    rules = load_architecture_rules(config_path)

    assert len(rules[0].calls) == 1
    assert rules[0].calls[0].receivers == ("kb", "keyboard")
    assert rules[0].calls[0].receiver_suffixes == (".kb", ".keyboard")
    assert rules[0].calls[0].methods == (
        "set_brightness",
        "set_color",
        "set_key_colors",
        "enable_user_mode",
        "turn_off",
        "set_effect",
    )
    assert rules[0].calls[0].required_locks == ("kb_lock", "engine.kb_lock", "self.kb_lock", "tray.engine.kb_lock")

    (tmp_path / "keyrgb/core/effects").mkdir(parents=True)
    (tmp_path / "keyrgb/core/effects/fades.py").write_text(
        "with kb_lock:\n    kb.set_color((1, 2, 3), brightness=1)\n",
        encoding="utf-8",
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
    assert report["rules"][0]["calls"][0]["allowed_files"] == ["keyrgb/core/effects/fades.py"]
    assert report["findings"] == []


def test_load_architecture_rules_parses_optional_locks_and_keyword_exemptions(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_poller_engine_call_rule_payload()), encoding="utf-8")

    call_rule = load_architecture_rules(config_path)[0].calls[1]

    assert call_rule.required_locks == ()
    assert [(item.name, item.equals) for item in call_rule.skip_if_keywords] == [("apply_to_hardware", False)]


@pytest.mark.parametrize("malformed", ["not a dict", 1, []])
def test_load_architecture_rules_rejects_non_dict_keyword_exemptions(tmp_path, malformed) -> None:
    payload = _poller_engine_call_rule_payload()
    payload["rules"][0]["calls"][1]["skip_if_keywords"] = [malformed]
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid keyword exemption"):
        load_architecture_rules(config_path)


def test_load_architecture_rules_parses_forbid_all_calls_with_empty_allowlist(tmp_path) -> None:
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbid_all_call_rule_payload()), encoding="utf-8")

    call_rule = load_architecture_rules(config_path)[0].calls[0]

    assert call_rule.allowed_files == ()
    assert call_rule.forbid_all is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["rules"][0]["calls"][0].update(forbid_all="yes"),
        lambda payload: payload["rules"][0]["calls"][0].update(forbid_all=False, allowed_files=[]),
    ],
)
def test_load_architecture_rules_rejects_malformed_forbid_all_call(tmp_path, mutate) -> None:
    payload = _forbid_all_call_rule_payload()
    mutate(payload)
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid call entry"):
        load_architecture_rules(config_path)
