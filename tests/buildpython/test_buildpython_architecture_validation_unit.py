from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import (
    ArchitectureScanResult,
    load_architecture_rules,
    scan_architecture,
)


def _call_rule_payload(
    *,
    allowed_files: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> dict:
    return {
        "rules": [
            {
                "id": "primary-lighting-write-ownership",
                "description": "Primary lighting writes",
                "severity": "error",
                "corpus": {
                    "include": ["keyrgb/**/*.py"],
                    "exclude": exclude_globs or [],
                },
                "calls": [
                    {
                        "receivers": ["kb", "keyboard"],
                        "receiver_suffixes": [".kb", ".keyboard"],
                        "methods": [
                            "set_brightness",
                            "set_color",
                            "set_key_colors",
                            "enable_user_mode",
                            "turn_off",
                            "set_effect",
                        ],
                        "allowed_files": allowed_files or ["keyrgb/core/effects/fades.py"],
                        "required_locks": ["kb_lock", "engine.kb_lock", "self.kb_lock", "tray.engine.kb_lock"],
                        "message": "unapproved primary lighting owner",
                        "lock_message": "unlocked primary lighting write",
                    }
                ],
            }
        ]
    }


def _scan_call_rule(
    tmp_path,
    source: str,
    *,
    relative_path: str = "keyrgb/core/effects/fades.py",
    exclude_globs: list[str] | None = None,
):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(_call_rule_payload(exclude_globs=exclude_globs)),
        encoding="utf-8",
    )
    return scan_architecture(root, load_architecture_rules(config_path))


def _assignment_rule_payload() -> dict:
    return {
        "rules": [
            {
                "id": "no-state-assignments",
                "description": "Observation modules do not mutate state",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "assignments": [
                    {
                        "targets": ["desired.exact", "named_expr"],
                        "target_suffixes": [".forbidden", ".compat"],
                        "message": "direct state assignment",
                    }
                ],
            }
        ]
    }


def _scan_assignment_rule(tmp_path, source: str, *, relative_path: str = "keyrgb/runtime.py"):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_assignment_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _forbidden_under_lock_payload() -> dict:
    return {
        "rules": [
            {
                "id": "no-blocking-under-lock",
                "description": "Blocking calls do not belong under the keyboard lock",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "forbidden_under_locks": [
                    {
                        "receivers": ["time"],
                        "methods": ["sleep"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "sleep under keyboard lock",
                    },
                    {
                        "receiver_suffixes": [".process"],
                        "methods": ["run"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "process run under keyboard lock",
                    },
                    {
                        "methods": ["join", "wait", "communicate"],
                        "match_any_receiver": True,
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "blocking method under keyboard lock",
                    },
                    {
                        "receivers": ["subprocess"],
                        "methods": ["run", "call", "check_call", "check_output", "Popen"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "subprocess under keyboard lock",
                    },
                ],
            }
        ]
    }


def _scan_forbidden_under_lock(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbidden_under_lock_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _lock_order_payload() -> dict:
    return {
        "rules": [
            {
                "id": "runtime-lock-order",
                "description": "Runtime lock order",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "lock_orders": [
                    {
                        "locks": [
                            {
                                "name": "_start_lock",
                                "aliases": ["self._start_lock", "engine._start_lock", "tray.engine._start_lock"],
                            },
                            {
                                "name": "kb_lock",
                                "aliases": ["self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                            },
                            {
                                "name": "_brightness_fade_lock",
                                "aliases": [
                                    "self._brightness_fade_lock",
                                    "engine._brightness_fade_lock",
                                    "tray.engine._brightness_fade_lock",
                                ],
                            },
                        ],
                        "message": "Runtime locks are out of order",
                    }
                ],
            }
        ]
    }


def _scan_lock_order(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_lock_order_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _poller_engine_call_rule_payload() -> dict:
    return {
        "rules": [
            {
                "id": "pollers-no-primary-engine-mutations",
                "description": "Pollers observe; approved leaves commit",
                "severity": "error",
                "corpus": {"include": ["keyrgb/tray/pollers/**/*.py"]},
                "calls": [
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["turn_off", "start_effect"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                        ],
                        "message": "poller primary engine mutation",
                    },
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["set_brightness"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                        ],
                        "skip_if_keywords": [{"name": "apply_to_hardware", "equals": False}],
                        "message": "poller primary brightness mutation",
                    },
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["stop"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                            "keyrgb/tray/pollers/hardware/_controller_sleep.py",
                        ],
                        "message": "poller primary engine stop",
                    },
                ],
            }
        ]
    }


def _scan_poller_engine_call(
    tmp_path,
    source: str,
    *,
    relative_path: str = "keyrgb/tray/pollers/hardware_polling.py",
):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_poller_engine_call_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _forbid_all_call_rule_payload(*, forbid_all: object = True, allowed_files: list[str] | None = None) -> dict:
    payload = _call_rule_payload(allowed_files=["keyrgb/core/effects/fades.py"])
    call = payload["rules"][0]["calls"][0]
    call["allowed_files"] = [] if allowed_files is None else allowed_files
    call["forbid_all"] = forbid_all
    return payload


def _scan_forbid_all_call_rule(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbid_all_call_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _scan_configured_secondary_device_rule(tmp_path, source: str, *, relative_path: str) -> ArchitectureScanResult:
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_root = Path(__file__).resolve().parents[2]
    rules = [
        rule
        for rule in load_architecture_rules(config_root / "buildpython/config/architecture_rules.json")
        if rule.rule_id == "secondary-device-no-primary-keyboard-mutations"
    ]
    return scan_architecture(root, rules)


def _scan_configured_rule(
    tmp_path,
    source: str,
    *,
    rule_id: str,
    relative_path: str,
) -> ArchitectureScanResult:
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    config_root = Path(__file__).resolve().parents[2]
    rules = [
        rule
        for rule in load_architecture_rules(config_root / "buildpython/config/architecture_rules.json")
        if rule.rule_id == rule_id
    ]
    return scan_architecture(root, rules)


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


def test_scan_lock_order_accepts_full_order_and_aliases(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """with self._start_lock:
    with engine.kb_lock:
        with tray.engine._brightness_fade_lock:
            pass
""",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "inner_lock", "outer_locks"),
    [
        ("with engine.kb_lock:\n    with self._start_lock:\n        pass\n", "_start_lock", ("engine.kb_lock",)),
        (
            "with tray.engine._brightness_fade_lock:\n    with kb_lock:\n        pass\n",
            "kb_lock",
            ("tray.engine._brightness_fade_lock",),
        ),
        (
            "with _brightness_fade_lock:\n    with self._start_lock:\n        pass\n",
            "_start_lock",
            ("_brightness_fade_lock",),
        ),
    ],
)
def test_scan_lock_order_reports_each_inversion(
    tmp_path, source: str, inner_lock: str, outer_locks: tuple[str, ...]
) -> None:
    result = _scan_lock_order(tmp_path, source)

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.line == 2
    assert finding.lock == inner_lock
    assert finding.outer_locks == outer_locks
    assert finding.regex.startswith("lock-order:")


def test_scan_lock_order_allows_same_level_reentrant_acquisition(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with kb_lock:\n    with self.kb_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_ignores_unrelated_locks(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with unrelated_lock:\n    with self._start_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_does_not_match_unconfigured_terminal_lock_names(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with other.kb_lock:\n    with self._start_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_supports_async_with(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """async def apply():
    async with self._start_lock:
        async with engine.kb_lock:
            async with tray.engine._brightness_fade_lock:
                pass
""",
    )

    assert result.findings == ()


def test_scan_lock_order_nested_function_does_not_inherit_outer_lock(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """with self._brightness_fade_lock:
    def later():
        with self._start_lock:
            pass
""",
    )

    assert result.findings == ()


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


def test_scan_architecture_forbid_all_reports_every_matching_call(tmp_path) -> None:
    result = _scan_forbid_all_call_rule(
        tmp_path,
        """engine.kb.set_brightness(5)
engine.kb.set_color((1, 2, 3), brightness=5)
""",
    )

    assert [finding.regex for finding in result.findings] == [
        "call:engine.kb.set_brightness",
        "call:engine.kb.set_color",
    ]


@pytest.mark.parametrize(
    ("receiver", "method"),
    [
        ("tray.engine.kb", "set_brightness"),
        ("tray.engine.kb", "set_color"),
        ("tray.engine.kb", "set_key_colors"),
        ("tray.engine.kb", "enable_user_mode"),
        ("tray.engine.kb", "turn_off"),
        ("tray.engine.kb", "set_effect"),
        ("tray.engine", "set_brightness"),
        ("tray.engine", "turn_off"),
        ("tray.engine", "start_effect"),
        ("tray.engine", "stop"),
        ("self.tray.engine.kb", "turn_off"),
        ("self.tray.engine", "stop"),
    ],
)
def test_configured_secondary_device_rule_forbids_each_primary_receiver_category(
    tmp_path, receiver: str, method: str
) -> None:
    result = _scan_configured_secondary_device_rule(
        tmp_path,
        f"{receiver}.{method}()\n",
        relative_path="keyrgb/tray/controllers/example_secondary.py",
    )

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "secondary-device-no-primary-keyboard-mutations"
    assert result.findings[0].regex == f"call:{receiver}.{method}"


def test_configured_secondary_device_rule_allows_secondary_receivers(tmp_path) -> None:
    result = _scan_configured_secondary_device_rule(
        tmp_path,
        """target.device.set_color((1, 2, 3), brightness=5)
selected.device.turn_off()
secondary.engine.turn_off()
engine.set_brightness(5)
""",
        relative_path="keyrgb/tray/controllers/example_secondary.py",
    )

    assert result.findings == ()


def test_configured_secondary_device_rule_uses_only_its_corpus(tmp_path) -> None:
    root = tmp_path / "repo"
    matching = root / "keyrgb/tray/controllers/example_secondary.py"
    explicit = root / "keyrgb/tray/controllers/_software_target_auxiliary.py"
    auxiliary = root / "keyrgb/tray/controllers/example_auxiliary.py"
    unrelated = root / "keyrgb/tray/controllers/ordinary.py"
    matching.parent.mkdir(parents=True)
    matching.write_text("tray.engine.turn_off()\n", encoding="utf-8")
    explicit.write_text("tray.engine.kb.turn_off()\n", encoding="utf-8")
    auxiliary.write_text("self.tray.engine.stop()\n", encoding="utf-8")
    unrelated.write_text("tray.engine.turn_off()\n", encoding="utf-8")
    config_root = Path(__file__).resolve().parents[2]

    rules = [
        rule
        for rule in load_architecture_rules(config_root / "buildpython/config/architecture_rules.json")
        if rule.rule_id == "secondary-device-no-primary-keyboard-mutations"
    ]
    result = scan_architecture(root, rules)

    assert [(finding.path, finding.regex) for finding in result.findings] == [
        ("keyrgb/tray/controllers/_software_target_auxiliary.py", "call:tray.engine.kb.turn_off"),
        ("keyrgb/tray/controllers/example_auxiliary.py", "call:self.tray.engine.stop"),
        ("keyrgb/tray/controllers/example_secondary.py", "call:tray.engine.turn_off"),
    ]


@pytest.mark.parametrize(
    ("source", "finding_token"),
    [
        (
            "from keyrgb.core.power.system import get_status\n",
            "import:keyrgb.core.power.system.get_status",
        ),
        (
            "from keyrgb.core.secondary_device_runtime import iter_effective_secondary_routes\n",
            "import:keyrgb.core.secondary_device_runtime.iter_effective_secondary_routes",
        ),
        (
            "import keyrgb.core.power.system as power_system\npower_system.get_status()\n",
            "call:keyrgb.core.power.system.get_status",
        ),
        (
            "import keyrgb.core.secondary_device_runtime as runtime\nruntime.iter_effective_secondary_routes()\n",
            "call:keyrgb.core.secondary_device_runtime.iter_effective_secondary_routes",
        ),
        (
            "tray.backend.probe()\n",
            "call:tray.backend.probe",
        ),
        (
            "backend.is_available()\n",
            "call:backend.is_available",
        ),
        (
            "engine._ensure_device_available()\n",
            "attribute:_ensure_device_available",
        ),
    ],
)
def test_configured_tray_ui_view_boundary_forbids_live_observation(tmp_path, source: str, finding_token: str) -> None:
    result = _scan_configured_rule(
        tmp_path,
        source,
        rule_id="tray-ui-no-live-observation",
        relative_path="keyrgb/tray/ui/menu.py",
    )

    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "tray-ui-no-live-observation"
    assert result.findings[0].regex == finding_token


def test_configured_tray_ui_view_boundary_allows_snapshot_reads(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        """from keyrgb.core.power.system import PowerMode, set_mode
from keyrgb.tray.controllers.view_snapshots import (
    read_effective_secondary_routes,
    read_system_power_status,
)

def render(tray):
    status = read_system_power_status(tray)
    routes = read_effective_secondary_routes(tray)
    available = tray.engine.device_available
    probe = tray.backend_probe.identifiers
    set_mode(PowerMode.BALANCED)
    return status, routes, available, probe
""",
        rule_id="tray-ui-no-live-observation",
        relative_path="keyrgb/tray/ui/menu_sections.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "from keyrgb.core.config.config import Config\n",
        "from keyrgb.core.config import Config\n",
    ],
)
def test_configured_diagnostics_rule_forbids_live_config(tmp_path, source: str) -> None:
    result = _scan_configured_rule(
        tmp_path,
        source,
        rule_id="diagnostics-no-live-config",
        relative_path="keyrgb/core/diagnostics/secondary_devices.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"diagnostics-no-live-config"}


def test_configured_diagnostics_rule_allows_readonly_settings_load(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        """from keyrgb.core.config._settings_view import ConfigSettingsView
from keyrgb.core.config.defaults import DEFAULTS
from keyrgb.core.config.file_storage import load_config_settings
from keyrgb.core.config.paths import config_file_path
""",
        rule_id="diagnostics-no-live-config",
        relative_path="keyrgb/core/diagnostics/secondary_devices.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "relative_path"),
    [
        ("tray._update_menu()\n", "keyrgb/tray/pollers/hardware_polling.py"),
        ("tray._refresh_ui(refresh_menu=True)\n", "keyrgb/tray/pollers/idle_power/_actions.py"),
        ("tray._refresh_ui(animate_icon=False, refresh_menu = True)\n", "keyrgb/core/power/management/manager.py"),
    ],
)
def test_configured_automatic_power_paths_cannot_rebuild_live_menu(tmp_path, source: str, relative_path: str) -> None:
    result = _scan_configured_rule(
        tmp_path,
        source,
        rule_id="automatic-power-paths-no-live-menu-rebuild",
        relative_path=relative_path,
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"automatic-power-paths-no-live-menu-rebuild"}


def test_configured_automatic_power_paths_allow_icon_refresh_without_menu(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        """tray._update_icon()
tray._refresh_ui(animate_icon=False, refresh_menu=False)
""",
        rule_id="automatic-power-paths-no-live-menu-rebuild",
        relative_path="keyrgb/tray/pollers/time_scheduler.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "from keyrgb.core.backends.policy import per_key_mode_policy\n",
        "from keyrgb.core.backends.sleep_state import is_controller_sleep_state\n",
        "from keyrgb.core.backends.policies import sleep_state\n",
        "import keyrgb.core.backends.policies as policies\n",
    ],
)
def test_configured_policy_import_rule_forbids_historical_and_package_root_imports(tmp_path, source: str) -> None:
    result = _scan_configured_rule(
        tmp_path,
        source,
        rule_id="canonical-backend-policy-imports",
        relative_path="keyrgb/tray/pollers/hardware/_controller_sleep.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"canonical-backend-policy-imports"}


def test_configured_policy_import_rule_allows_canonical_leaf_imports(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        """from keyrgb.core.backends.policies.sleep_state import is_controller_sleep_state
from keyrgb.core.backends.policies.per_key_mode import per_key_mode_policy
from keyrgb.core.backends.policies.backend_selection import stability_for_backend
""",
        rule_id="canonical-backend-policy-imports",
        relative_path="keyrgb/tray/pollers/hardware/_controller_sleep.py",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "globals().update({'render': render})\n",
        "api = sys.modules[__name__]\n",
    ],
)
def test_configured_reactive_rule_forbids_module_global_injection(tmp_path, source: str) -> None:
    result = _scan_configured_rule(
        tmp_path,
        source,
        rule_id="reactive-no-module-global-injection",
        relative_path="keyrgb/core/effects/reactive/effects.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"reactive-no-module-global-injection"}


def test_configured_reactive_rule_allows_explicit_facade_construction(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        """# Build immutable API facades (replaces globals().update + sys.modules cast)
from keyrgb.core.effects.reactive._effects_api import build_reactive_api

_fade_api = build_reactive_api()
""",
        rule_id="reactive-no-module-global-injection",
        relative_path="keyrgb/core/effects/reactive/effects.py",
    )

    assert result.findings == ()


def test_configured_gui_async_rule_forbids_direct_worker_threads(tmp_path) -> None:
    result = _scan_configured_rule(
        tmp_path,
        "from threading import Thread\nThread(target=work, daemon=True).start()\n",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/windows/uniform.py",
    )

    assert result.findings
    assert {finding.rule_id for finding in result.findings} == {"gui-background-work-uses-tk-async"}


def test_configured_gui_async_rule_allows_tk_async_owner_and_helpers(tmp_path) -> None:
    owner = _scan_configured_rule(
        tmp_path,
        "Thread(target=worker, daemon=True).start()\n",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/utils/tk_async.py",
    )
    helper = _scan_configured_rule(
        tmp_path,
        """from keyrgb.gui.utils.tk_async import TkAsyncCoordinator, submit_gui_work

self.tk_jobs = TkAsyncCoordinator()
submit_gui_work(self, self.root, work, on_done)
""",
        rule_id="gui-background-work-uses-tk-async",
        relative_path="keyrgb/gui/windows/power_mode.py",
    )

    assert owner.findings == ()
    assert helper.findings == ()


@pytest.mark.parametrize("method", ["turn_off", "start_effect"])
def test_poller_engine_mutations_are_forbidden_outside_commit_leaves(tmp_path, method: str) -> None:
    result = _scan_poller_engine_call(tmp_path, f"tray.engine.{method}()\n")

    assert len(result.findings) == 1
    assert result.findings[0].message == "poller primary engine mutation"
    assert result.findings[0].regex == f"call:tray.engine.{method}"


def test_poller_engine_stop_is_forbidden_outside_commit_leaves(tmp_path) -> None:
    result = _scan_poller_engine_call(tmp_path, "tray.engine.stop()\n")

    assert len(result.findings) == 1
    assert result.findings[0].message == "poller primary engine stop"


@pytest.mark.parametrize(
    "relative_path",
    [
        "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
        "keyrgb/tray/pollers/idle_power/_action_execution.py",
    ],
)
def test_poller_turn_off_commit_leaves_are_allowed(tmp_path, relative_path: str) -> None:
    result = _scan_poller_engine_call(tmp_path, "tray.engine.turn_off()\n", relative_path=relative_path)

    assert result.findings == ()


@pytest.mark.parametrize(
    "relative_path",
    [
        "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
        "keyrgb/tray/pollers/idle_power/_action_execution.py",
        "keyrgb/tray/pollers/hardware/_controller_sleep.py",
    ],
)
def test_poller_stop_commit_leaves_are_allowed(tmp_path, relative_path: str) -> None:
    result = _scan_poller_engine_call(tmp_path, "tray.engine.stop()\n", relative_path=relative_path)

    assert result.findings == ()


def test_poller_non_brightness_mutation_cannot_use_brightness_keyword_exemption(tmp_path) -> None:
    result = _scan_poller_engine_call(
        tmp_path,
        "tray.engine.turn_off(apply_to_hardware=False)\n",
    )

    assert len(result.findings) == 1
    assert result.findings[0].regex == "call:tray.engine.turn_off"


def test_poller_cache_only_brightness_is_exempt(tmp_path) -> None:
    result = _scan_poller_engine_call(
        tmp_path,
        "tray.engine.set_brightness(5, apply_to_hardware=False)\n",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    "source",
    [
        "tray.engine.set_brightness(5, apply_to_hardware=True)\n",
        "tray.engine.set_brightness(5, apply_to_hardware=0)\n",
        "tray.engine.set_brightness(5)\n",
        "apply = False\ntray.engine.set_brightness(5, apply_to_hardware=apply)\n",
    ],
)
def test_poller_hardware_brightness_requires_literal_false_exemption(tmp_path, source: str) -> None:
    result = _scan_poller_engine_call(tmp_path, source)

    assert len(result.findings) == 1
    assert result.findings[0].regex == "call:tray.engine.set_brightness"


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


def test_current_repo_has_no_architecture_findings() -> None:
    root = Path(__file__).resolve().parents[2]
    rules = load_architecture_rules(root / "buildpython/config/architecture_rules.json")

    assert scan_architecture(root, rules).findings == ()


def test_configured_hardware_assignment_rule_is_scoped_and_keeps_is_off_allowed(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/tray/pollers/hardware/nested").mkdir(parents=True)
    (root / "keyrgb/tray/pollers/hardware/nested/example.py").write_text(
        "tray.config.brightness = 25\ntray._power_forced_off = True\ntray.is_off = True\n",
        encoding="utf-8",
    )
    (root / "keyrgb/tray/pollers/hardware_polling.py").write_text(
        "tray.config.effect = 'none'\ntray.idle_forced_off = True\n",
        encoding="utf-8",
    )
    (root / "keyrgb/tray/other.py").parent.mkdir(parents=True, exist_ok=True)
    (root / "keyrgb/tray/other.py").write_text("tray.config.brightness = 25\n", encoding="utf-8")
    config_root = Path(__file__).resolve().parents[2]

    rules = load_architecture_rules(config_root / "buildpython/config/architecture_rules.json")
    findings = scan_architecture(root, rules).findings

    assignment_findings = [
        finding for finding in findings if finding.rule_id == "hardware-observation-no-desired-state-assignments"
    ]
    assert [(finding.path, finding.line, finding.regex) for finding in assignment_findings] == [
        ("keyrgb/tray/pollers/hardware/nested/example.py", 1, "assignment:tray.config.brightness"),
        ("keyrgb/tray/pollers/hardware/nested/example.py", 2, "assignment:tray._power_forced_off"),
        ("keyrgb/tray/pollers/hardware_polling.py", 1, "assignment:tray.config.effect"),
        ("keyrgb/tray/pollers/hardware_polling.py", 2, "assignment:tray.idle_forced_off"),
    ]


def test_scan_architecture_assignment_rules_covers_all_assignment_forms_and_destructuring(tmp_path) -> None:
    result = _scan_assignment_rule(
        tmp_path,
        """desired.exact = 1
ann.forbidden: int = 2
aug.compat += 1
(first.forbidden, [nested.compat, irrelevant]) = (1, 2, 3)
named_expr = 5
(named_expr := 6)
""",
    )

    assert [(finding.line, finding.regex) for finding in result.findings] == [
        (1, "assignment:desired.exact"),
        (2, "assignment:ann.forbidden"),
        (3, "assignment:aug.compat"),
        (4, "assignment:first.forbidden"),
        (4, "assignment:nested.compat"),
        (5, "assignment:named_expr"),
        (6, "assignment:named_expr"),
    ]


def test_scan_architecture_assignment_rules_match_exact_and_terminal_suffix_only(tmp_path) -> None:
    result = _scan_assignment_rule(
        tmp_path,
        """desired.exact = 1
other.forbidden = 2
other.compat = 3
other.forbidden_extra = 4
unrelated.value = 5
""",
    )

    assert [finding.regex for finding in result.findings] == [
        "assignment:desired.exact",
        "assignment:other.forbidden",
        "assignment:other.compat",
    ]


def test_scan_architecture_assignment_rules_do_not_ban_observational_is_off_assignment(tmp_path) -> None:
    result = _scan_assignment_rule(tmp_path, "tray.is_off = True\n")

    assert result.findings == ()


def test_scan_architecture_call_rule_reports_unapproved_owner(tmp_path) -> None:
    result = _scan_call_rule(
        tmp_path, "engine.kb.set_color((1, 2, 3), brightness=1)\n", relative_path="keyrgb/core/other.py"
    )

    assert len(result.findings) == 1
    assert result.findings[0].message == "unapproved primary lighting owner"
    assert result.findings[0].regex == "call:engine.kb.set_color"


def test_scan_architecture_call_rule_reports_approved_unlocked_write(tmp_path) -> None:
    result = _scan_call_rule(tmp_path, "engine.kb.set_color((1, 2, 3), brightness=1)\n")

    assert len(result.findings) == 1
    assert result.findings[0].message == "unlocked primary lighting write"


def test_scan_architecture_call_rule_accepts_approved_locked_write(tmp_path) -> None:
    result = _scan_call_rule(tmp_path, "with engine.kb_lock:\n    engine.kb.set_color((1, 2, 3), brightness=1)\n")

    assert result.findings == ()


def test_scan_architecture_call_rule_is_selective_to_receivers_and_methods(tmp_path) -> None:
    result = _scan_call_rule(
        tmp_path,
        """with engine.kb_lock:
    engine.kb.get_brightness()
    engine.set_color((1, 2, 3), brightness=1)
    other.device.set_color((1, 2, 3), brightness=1)
    engine.kb.set_color((1, 2, 3), brightness=1)
""",
    )

    assert result.findings == ()


def test_scan_architecture_call_rule_matches_keyboard_aliases(tmp_path) -> None:
    result = _scan_call_rule(
        tmp_path,
        "with kb_lock:\n    tray.kb.set_brightness(5)\n    keyboard.set_color((1, 2, 3), brightness=5)\n",
    )

    assert result.findings == ()


def test_scan_architecture_call_rule_tracks_async_and_nested_scope_locks(tmp_path) -> None:
    result = _scan_call_rule(
        tmp_path,
        """async def apply():
    async with kb_lock:
        kb.set_brightness(5)
        class Immediate:
            kb.set_color((1, 2, 3), brightness=5)
        def later(value=kb.set_effect(payload)):
            kb.set_brightness(10)
""",
    )

    assert len(result.findings) == 1
    assert result.findings[0].regex == "call:kb.set_brightness"
    assert result.findings[0].line == 7


def test_scan_architecture_call_rule_exempts_backend_implementations(tmp_path) -> None:
    result = _scan_call_rule(
        tmp_path,
        "self.kb.set_brightness(5)\n",
        relative_path="keyrgb/core/backends/sysfs_leds/device.py",
        exclude_globs=["keyrgb/core/backends/**/*.py"],
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "method"),
    [
        ("with kb_lock:\n    time.sleep(1)\n", "time.sleep"),
        ("with self.kb_lock:\n    worker.join()\n", "worker.join"),
        ("with kb_lock:\n    process.wait()\n", "process.wait"),
        ("with kb_lock:\n    process.communicate()\n", "process.communicate"),
        ("with kb_lock:\n    subprocess.run([])\n", "subprocess.run"),
        ("with kb_lock:\n    subprocess.call([])\n", "subprocess.call"),
        ("with kb_lock:\n    subprocess.check_call([])\n", "subprocess.check_call"),
        ("with kb_lock:\n    subprocess.check_output([])\n", "subprocess.check_output"),
        ("with kb_lock:\n    subprocess.Popen([])\n", "subprocess.Popen"),
    ],
)
def test_forbidden_under_lock_reports_blocking_call(tmp_path, source: str, method: str) -> None:
    result = _scan_forbidden_under_lock(tmp_path, source)

    assert len(result.findings) == 1
    assert result.findings[0].regex == f"forbidden-under-lock:{method}"
    assert result.findings[0].lock in {"kb_lock", "self.kb_lock"}


@pytest.mark.parametrize("lock", ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"])
@pytest.mark.parametrize(
    ("imports", "call", "method"),
    [
        ("from time import sleep", "sleep(1)", "time.sleep"),
        ("from time import sleep as pause", "pause(1)", "time.sleep"),
        ("import time as clock", "clock.sleep(1)", "time.sleep"),
        ("from subprocess import run", "run([])", "subprocess.run"),
        ("from subprocess import run as launch", "launch([])", "subprocess.run"),
        ("import subprocess as commands", "commands.run([])", "subprocess.run"),
        ("from subprocess import Popen", "Popen([])", "subprocess.Popen"),
        ("from subprocess import Popen as launch", "launch([])", "subprocess.Popen"),
        ("import subprocess as commands", "commands.Popen([])", "subprocess.Popen"),
    ],
)
def test_forbidden_under_lock_canonicalizes_imported_and_module_aliases(
    tmp_path, lock: str, imports: str, call: str, method: str
) -> None:
    result = _scan_forbidden_under_lock(tmp_path, f"{imports}\nwith {lock}:\n    {call}\n")

    assert len(result.findings) == 1
    assert result.findings[0].regex == f"forbidden-under-lock:{method}"
    assert result.findings[0].lock == lock


def test_forbidden_under_lock_does_not_treat_shadowed_callback_as_subprocess_run(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        "from subprocess import run\ndef invoke(run):\n    with kb_lock:\n        run([])\n",
    )

    assert result.findings == ()


def test_forbidden_under_lock_supports_suffix_and_match_any_receivers(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """with kb_lock:
    service.process.run([])
    thread.join()
    event.wait()
    child.communicate()
""",
    )

    assert [finding.regex for finding in result.findings] == [
        "forbidden-under-lock:service.process.run",
        "forbidden-under-lock:thread.join",
        "forbidden-under-lock:event.wait",
        "forbidden-under-lock:child.communicate",
    ]


def test_forbidden_under_lock_allows_outside_lock_and_nonblocking_calls(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """time.sleep(1)
with kb_lock:
    keyboard.set_color((1, 2, 3))
    thread.start()
""",
    )

    assert result.findings == ()


def test_forbidden_under_lock_supports_async_with_and_nested_function_scope(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """async def apply():
    async with self.kb_lock:
        time.sleep(1)
        def later():
            time.sleep(1)
""",
    )

    assert len(result.findings) == 1
    assert result.findings[0].line == 3


def test_forbidden_under_lock_does_not_include_bare_methods_or_arbitrary_callbacks(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """with kb_lock:
    sleep(1)
    callback()
""",
    )

    assert result.findings == ()


def test_scan_architecture_reports_matches_and_respects_excludes(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/core").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)

    (root / "keyrgb/core/bad.py").write_text(
        "from keyrgb.tray.app.application import App\n",
        encoding="utf-8",
    )
    (root / "tests/ignored.py").write_text(
        "from keyrgb.tray.app.application import App\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "core-boundary",
                        "description": "Core boundary",
                        "severity": "error",
                        "corpus": {
                            "include": ["keyrgb/**/*.py"],
                            "exclude": ["tests/**"],
                        },
                        "patterns": [
                            {
                                "regex": "^\\s*(?:from|import)\\s+keyrgb\\.tray\\b",
                                "flags": "m",
                                "message": "No tray import",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)
    result = scan_architecture(root, rules)

    assert result.rules_checked == 1
    assert result.scanned_files == 1
    assert len(result.findings) == 1
    assert result.findings[0].path == "keyrgb/core/bad.py"
    assert result.findings[0].line == 1
    assert result.findings[0].rule_id == "core-boundary"


def test_scan_architecture_reports_import_rule_matches_and_respects_excludes(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/gui/windows").mkdir(parents=True)

    (root / "keyrgb/gui/windows/uniform.py").write_text(
        "from keyrgb.core.backends.registry import select_backend\n",
        encoding="utf-8",
    )
    (root / "keyrgb/gui/windows/_runtime.py").write_text(
        "from keyrgb.core.backends.registry import select_backend\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "gui-window-no-direct-backend-selection",
                        "description": "GUI windows should not import backend selection directly.",
                        "severity": "warning",
                        "corpus": {
                            "include": ["keyrgb/gui/windows/**/*.py"],
                            "exclude": ["keyrgb/gui/windows/_*.py"],
                        },
                        "imports": [
                            {
                                "module": "keyrgb.core.backends.registry",
                                "message": "GUI window modules should not import backend selection directly.",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)
    result = scan_architecture(root, rules)

    assert result.rules_checked == 1
    assert result.scanned_files == 1
    assert len(result.findings) == 1
    assert result.findings[0].path == "keyrgb/gui/windows/uniform.py"
    assert result.findings[0].line == 1
    assert result.findings[0].rule_id == "gui-window-no-direct-backend-selection"
    assert result.findings[0].regex == "import:keyrgb.core.backends.registry"


def test_scan_architecture_matches_importfrom_submodule_extensions(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/tray/ui").mkdir(parents=True)
    (root / "keyrgb/tray/ui/menu_status.py").write_text(
        "from keyrgb.core.profile import profiles\n",
        encoding="utf-8",
    )

    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "tray-ui-no-direct-profile-storage",
                        "description": "Tray UI should not import profile storage directly.",
                        "severity": "warning",
                        "corpus": {
                            "include": ["keyrgb/tray/ui/**/*.py"],
                        },
                        "imports": [
                            {
                                "module": "keyrgb.core.profile.profiles",
                                "message": "Tray UI should not import core profile storage directly.",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)
    result = scan_architecture(root, rules)

    assert len(result.findings) == 1
    assert result.findings[0].path == "keyrgb/tray/ui/menu_status.py"
    assert result.findings[0].line == 1
    assert result.findings[0].regex == "import:keyrgb.core.profile.profiles"


def test_scan_architecture_reports_attribute_rule_matches(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/tray/ui").mkdir(parents=True)
    (root / "keyrgb/tray/ui/menu_sections.py").write_text(
        "def update(tray):\n    tray._update_menu()\n    tray._system_power_last_ok = False\n",
        encoding="utf-8",
    )

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
                            },
                            {
                                "name": "_system_power_last_ok",
                                "message": "Tray UI should not mutate private tray runtime state directly",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rules = load_architecture_rules(config_path)
    result = scan_architecture(root, rules)

    assert len(result.findings) == 2
    assert [finding.line for finding in result.findings] == [2, 3]
    assert [finding.regex for finding in result.findings] == [
        "attribute:_update_menu",
        "attribute:_system_power_last_ok",
    ]


def test_scan_architecture_attribute_rules_ignore_private_method_definitions(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "keyrgb/tray/ui").mkdir(parents=True)
    (root / "keyrgb/tray/ui/protocols.py").write_text(
        "class Demo:\n    def _update_menu(self):\n        return None\n",
        encoding="utf-8",
    )

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
    result = scan_architecture(root, rules)

    assert result.findings == ()


def test_architecture_validation_runner_fails_on_warning_findings(monkeypatch, tmp_path) -> None:
    (tmp_path / "keyrgb/tray/ui").mkdir(parents=True)
    (tmp_path / "keyrgb/tray/ui/menu.py").write_text(
        "from keyrgb.core.backends.registry import select_backend\n",
        encoding="utf-8",
    )
    (tmp_path / "buildpython/config").mkdir(parents=True)
    (tmp_path / "buildpython/config/architecture_rules.json").write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "tray-ui-no-backend-selection",
                        "description": "demo",
                        "severity": "warning",
                        "corpus": {"include": ["keyrgb/tray/ui/**/*.py"]},
                        "patterns": [
                            {
                                "regex": "^\\s*(?:from|import)\\s+keyrgb\\.core\\.backends\\.registry\\b",
                                "flags": "m",
                                "message": "no registry",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "buildlog")

    result = step_architecture_validation.architecture_validation_runner()

    assert result.exit_code == 1
    assert "Warnings: 1" in result.stdout


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
