from __future__ import annotations

import json

import pytest

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture
from tests.buildpython._architecture_validation_unit_support import (
    _scan_assignment_rule,
    _scan_call_rule,
    _scan_forbid_all_call_rule,
    _scan_poller_engine_call,
)


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
