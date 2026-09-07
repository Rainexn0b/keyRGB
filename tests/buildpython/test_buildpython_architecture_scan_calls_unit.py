from __future__ import annotations

import pytest

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
