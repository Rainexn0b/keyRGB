from __future__ import annotations

import json
import re

import pytest

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture


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
                        "methods": ["set_brightness", "set_color", "set_key_colors", "enable_user_mode", "turn_off", "set_effect"],
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


def test_scan_architecture_call_rule_reports_unapproved_owner(tmp_path) -> None:
    result = _scan_call_rule(tmp_path, "engine.kb.set_color((1, 2, 3), brightness=1)\n", relative_path="keyrgb/core/other.py")

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
