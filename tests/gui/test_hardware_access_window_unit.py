from __future__ import annotations

import json
from pathlib import Path

from keyrgb.gui.hardware_access import HardwareAccessOutcome
from keyrgb.gui.hardware_access_offer import (
    RuleCompare,
    compare_installed_rules,
    format_setup_result,
    offer_dismissed,
    remember_offer_dismissed,
    setup_explanation,
    should_auto_offer,
)
from keyrgb.gui.hardware_access_window import HardwareAccessSetupController


def _outcome(name: str, detail: str = "", written: str | None = "none") -> HardwareAccessOutcome:
    return HardwareAccessOutcome(
        outcome=name,
        detail=detail,
        written=written,
        returncode=0,
        stdout="",
        stderr="",
        terminal_command="install.sh --hardware-access-only",
    )


def test_explanation_states_optional_access_and_removal() -> None:
    text = setup_explanation()
    assert "observing keypresses" in text
    assert "video group" in text
    assert "Log out and back in" in text
    assert "Power controls are included" in text
    assert "Skipping setup does not remove" in text
    assert "manual deletion of the managed filenames" in text
    assert "does not uninstall" in text


def test_auto_offer_requires_evidence_and_honors_dismissal() -> None:
    empty = RuleCompare()
    stale = RuleCompare(stale=("99-ite8291-wootbook.rules",))
    missing = RuleCompare(missing=("99-ite8291-wootbook.rules",))

    assert should_auto_offer(permission_denied=False, compare=empty, dismissed=False) is False
    assert should_auto_offer(permission_denied=False, compare=missing, dismissed=False) is False
    assert should_auto_offer(permission_denied=True, compare=empty, dismissed=False) is True
    assert should_auto_offer(permission_denied=True, compare=empty, dismissed=True) is False
    assert should_auto_offer(permission_denied=False, compare=stale, dismissed=False) is True
    assert should_auto_offer(permission_denied=False, compare=stale, dismissed=True) is False


def test_compare_distinguishes_stale_missing_and_foreign(tmp_path: Path) -> None:
    payload = tmp_path / "system"
    rules = tmp_path / "rules"
    payload.joinpath("udev").mkdir(parents=True)
    rules.mkdir()
    bundled = "KEYRGB_MANAGED_UDEV_RULE=usb-hidraw\ncurrent\n"
    (payload / "udev/99-ite8291-wootbook.rules").write_text(bundled, encoding="utf-8")
    (rules / "99-ite8291-wootbook.rules").write_text(
        "KEYRGB_MANAGED_UDEV_RULE=usb-hidraw\nold\n",
        encoding="utf-8",
    )
    (rules / "99-keyrgb-sysfs-leds.rules").write_text("# vendor only\n", encoding="utf-8")

    compared = compare_installed_rules(payload, rules_dir=rules)

    assert compared.stale == ("99-ite8291-wootbook.rules",)
    assert "99-keyrgb-sysfs-leds.rules" in compared.foreign
    assert "99-keyrgb-input-uaccess.rules" in compared.missing


def test_installed_result_does_not_claim_usable_hardware() -> None:
    text = format_setup_result(_outcome("installed"), in_video=True)
    assert "usable" in text
    assert "not mean the keyboard is usable" in text

    blocked = format_setup_result(_outcome("installed"), in_video=False)
    assert "not in the video group" in blocked
    assert "Log out and back in" in blocked
    assert "usable yet" in blocked

    added = format_setup_result(_outcome("installed", "video-group=added"), in_video=False)
    assert "added to the video group" in added
    assert "does not add" not in added


def test_unknown_write_state_is_not_reported_as_clean() -> None:
    text = format_setup_result(_outcome("failed", "missing-result", None), in_video=True)
    assert "unknown" in text
    assert "Nothing was written" not in text


def test_not_now_records_dismissal_without_a_configured_flag(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"effect": "none"}), encoding="utf-8")
    statuses: list[str] = []
    controller = HardwareAccessSetupController(
        on_status=statuses.append,
        remember_dismissal=lambda: remember_offer_dismissed(config_file=config_file),
        in_video=True,
    )

    controller.not_now()

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["hardware_access_offer_dismissed"] is True
    assert "configured" not in saved
    assert saved["effect"] == "none"
    assert offer_dismissed(config_file=config_file) is True
    assert controller.dismissed is True


def test_duplicate_submission_is_ignored_until_complete() -> None:
    statuses: list[str] = []
    controller = HardwareAccessSetupController(
        on_status=statuses.append, remember_dismissal=lambda: True, in_video=True
    )

    assert controller.start() is True
    assert controller.start() is False
    controller.complete(_outcome("cancelled"))
    assert controller.busy is False
    assert "Nothing was written" in statuses[-1]
    assert controller.start() is True


def test_settings_action_is_not_gated_by_dismissal() -> None:
    text = Path("keyrgb/gui/settings/panels/version_panel.py").read_text(encoding="utf-8")
    assert "Set up hardware access…" in text
    assert "hardware_access_offer_dismissed" not in text
    window = Path("keyrgb/gui/hardware_access_window.py").read_text(encoding="utf-8")
    assert "setup_workflow" not in window
