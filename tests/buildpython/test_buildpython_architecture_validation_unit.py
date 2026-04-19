from __future__ import annotations

import json
import re

import pytest

import buildpython.steps.step_architecture_validation as step_architecture_validation

from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture


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
                            "include": ["src/**/*.py"],
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
    assert rules[0].include_globs == ("src/**/*.py",)
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
                            "include": ["src/gui/**/*.py"],
                        },
                        "imports": [
                            {
                                "module": "src.core.backends.registry",
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
    assert rules[0].imports[0].module == "src.core.backends.registry"
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
                            "include": ["src/tray/ui/**/*.py"],
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


def test_scan_architecture_reports_matches_and_respects_excludes(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src/core").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)

    (root / "src/core/bad.py").write_text(
        "from src.tray.app.application import App\n",
        encoding="utf-8",
    )
    (root / "tests/ignored.py").write_text(
        "from src.tray.app.application import App\n",
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
                            "include": ["src/**/*.py"],
                            "exclude": ["tests/**"],
                        },
                        "patterns": [
                            {
                                "regex": "^\\s*(?:from|import)\\s+src\\.tray\\b",
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
    assert result.findings[0].path == "src/core/bad.py"
    assert result.findings[0].line == 1
    assert result.findings[0].rule_id == "core-boundary"


def test_scan_architecture_reports_import_rule_matches_and_respects_excludes(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src/gui/windows").mkdir(parents=True)

    (root / "src/gui/windows/uniform.py").write_text(
        "from src.core.backends.registry import select_backend\n",
        encoding="utf-8",
    )
    (root / "src/gui/windows/_runtime.py").write_text(
        "from src.core.backends.registry import select_backend\n",
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
                            "include": ["src/gui/windows/**/*.py"],
                            "exclude": ["src/gui/windows/_*.py"],
                        },
                        "imports": [
                            {
                                "module": "src.core.backends.registry",
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
    assert result.findings[0].path == "src/gui/windows/uniform.py"
    assert result.findings[0].line == 1
    assert result.findings[0].rule_id == "gui-window-no-direct-backend-selection"
    assert result.findings[0].regex == "import:src.core.backends.registry"


def test_scan_architecture_matches_importfrom_submodule_extensions(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src/tray/ui").mkdir(parents=True)
    (root / "src/tray/ui/menu_status.py").write_text(
        "from src.core.profile import profiles\n",
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
                            "include": ["src/tray/ui/**/*.py"],
                        },
                        "imports": [
                            {
                                "module": "src.core.profile.profiles",
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
    assert result.findings[0].path == "src/tray/ui/menu_status.py"
    assert result.findings[0].line == 1
    assert result.findings[0].regex == "import:src.core.profile.profiles"


def test_scan_architecture_reports_attribute_rule_matches(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src/tray/ui").mkdir(parents=True)
    (root / "src/tray/ui/menu_sections.py").write_text(
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
                            "include": ["src/tray/ui/**/*.py"],
                        },
                        "attributes": [
                            {
                                "name": "_update_menu",
                                "message": "Tray UI should not call private runtime menu refresh hooks directly",
                            },
                            {
                                "name": "_system_power_last_ok",
                                "message": "Tray UI should not mutate private tray runtime state directly",
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

    assert len(result.findings) == 2
    assert [finding.line for finding in result.findings] == [2, 3]
    assert [finding.regex for finding in result.findings] == [
        "attribute:_update_menu",
        "attribute:_system_power_last_ok",
    ]


def test_scan_architecture_attribute_rules_ignore_private_method_definitions(tmp_path) -> None:
    root = tmp_path / "repo"
    (root / "src/tray/ui").mkdir(parents=True)
    (root / "src/tray/ui/protocols.py").write_text(
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
                            "include": ["src/tray/ui/**/*.py"],
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


def test_architecture_validation_runner_returns_run_result_for_recoverable_rule_errors(
    monkeypatch, tmp_path
) -> None:
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
