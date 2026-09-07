from __future__ import annotations

import json

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture


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
