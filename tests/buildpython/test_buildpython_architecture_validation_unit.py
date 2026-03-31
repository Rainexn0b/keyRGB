from __future__ import annotations

import json
import re

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