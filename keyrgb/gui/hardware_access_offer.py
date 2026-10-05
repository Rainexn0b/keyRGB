"""Offer and result rules for hardware-access setup.

This is not the per-key calibrator. Permission checks must not consult the
dismissal flag stored here.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from keyrgb.core.config.file_storage import merge_config_settings_atomic
from keyrgb.core.config.paths import config_file_path
from keyrgb.gui.hardware_access import HardwareAccessOutcome, terminal_command

logger = logging.getLogger(__name__)

DISMISSAL_KEY = "hardware_access_offer_dismissed"

_RULES = (
    (
        "udev/99-ite8291-wootbook.rules",
        "99-ite8291-wootbook.rules",
        (
            "KEYRGB_MANAGED_UDEV_RULE=usb-hidraw",
            "Allow user access to ITE 8291 USB device.",
            "Allow user access to supported ITE / Lenovo USB / hidraw devices.",
        ),
    ),
    (
        "udev/99-keyrgb-sysfs-leds.rules",
        "99-keyrgb-sysfs-leds.rules",
        (
            "KEYRGB_MANAGED_UDEV_RULE=sysfs-leds",
            "Allow KeyRGB to write keyboard backlight sysfs LED attributes.",
        ),
    ),
    (
        "udev/99-keyrgb-input-uaccess.rules",
        "99-keyrgb-input-uaccess.rules",
        (
            "KEYRGB_MANAGED_UDEV_RULE=input-uaccess",
            "Reactive Typing effects",
            "for reactive effects.",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RuleCompare:
    """Bundled-versus-installed rule state. Missing files are not errors."""

    stale: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    foreign: tuple[str, ...] = ()


def setup_explanation() -> str:
    """Text shown before authorization. Optional access stays unchecked in the UI."""

    return (
        "KeyRGB can install the keyboard USB and sysfs access rules already bundled with this version. "
        "The sysfs rule assigns keyboard backlight files to the video group. "
        "Your user needs to be in video; logging out and back in will not fix that by itself if you are not in the group. "
        "Reactive input is separate and allows observing keypresses, not just lighting changes. "
        "Power controls are also separate. "
        "Skipping setup does not remove files already installed. "
        "Removal is the existing uninstaller or manual deletion of the managed filenames. "
        "This window does not uninstall."
    )


def should_auto_offer(
    *,
    permission_denied: bool,
    compare: RuleCompare,
    dismissed: bool,
) -> bool:
    """Return whether an automatic prompt is justified.

    A missing rule file is not enough. Catalog and test machines without a
    managed rule must not be prompted. Dismissal suppresses only this prompt.
    """

    if dismissed:
        return False
    if permission_denied:
        return True
    return bool(compare.stale)


def compare_installed_rules(
    payload_dir: Path,
    *,
    rules_dir: Path = Path("/etc/udev/rules.d"),
) -> RuleCompare:
    """Compare bundled rule bytes with installed managed copies.

    A missing installed file is recorded, not treated as a failure. A file that
    is not KeyRGB-managed is foreign and is not a stale-rule offer.
    """

    stale: list[str] = []
    missing: list[str] = []
    foreign: list[str] = []
    for relative, installed_name, markers in _RULES:
        bundled = payload_dir / relative
        installed = rules_dir / installed_name
        if not installed.is_file():
            missing.append(installed_name)
            continue
        try:
            installed_text = installed.read_text(encoding="utf-8", errors="replace")
            bundled_bytes = bundled.read_bytes() if bundled.is_file() else None
            installed_bytes = installed.read_bytes()
        except OSError:
            missing.append(installed_name)
            continue
        if bundled_bytes is not None and installed_bytes == bundled_bytes:
            continue
        if any(marker in installed_text for marker in markers):
            stale.append(installed_name)
        else:
            foreign.append(installed_name)
    return RuleCompare(stale=tuple(stale), missing=tuple(missing), foreign=tuple(foreign))


def user_in_video(group_names: Sequence[str]) -> bool:
    return "video" in group_names


def format_setup_result(
    outcome: HardwareAccessOutcome,
    *,
    in_video: bool | None,
) -> str:
    """User-facing result. A successful write is not a claim of usable hardware."""

    lines = [f"{outcome.outcome}: {outcome.detail}".strip()]
    if outcome.outcome == "installed":
        lines = ["Hardware-access files were installed or already current."]
        if in_video is False:
            lines.append(
                "Activation is incomplete. The sysfs rule needs your user to be in the video group. "
                "Logging out and back in will not fix that, because this setup does not add the group."
            )
        else:
            lines.append(
                "Access is not confirmed. Seat ACLs may still need a replug, a new login, or a reboot. "
                "This result does not mean the keyboard is usable yet."
            )
    elif outcome.outcome == "cancelled":
        lines = ["Authorization was dismissed. Nothing was written."]
    elif outcome.outcome == "authorization-failed":
        lines = [
            "Authorization failed or no graphical agent was available.",
            f"You can run this in a terminal instead: {outcome.terminal_command}",
        ]
    elif outcome.outcome == "prerequisite":
        lines = [
            f"Setup did not start: {outcome.detail}.",
            f"Terminal command: {outcome.terminal_command}",
        ]
    elif outcome.outcome == "conflict":
        lines = [f"A destination is not a KeyRGB-managed file and was not replaced: {outcome.detail}."]
    elif outcome.written == "none":
        lines.append("Nothing was written.")
    elif outcome.written is None:
        lines.append("The write state is unknown. Do not assume the rules are unchanged.")
    else:
        lines.append(f"Files written: {outcome.written}.")
    return "\n".join(lines)


def offer_dismissed(*, config_file: Path | None = None) -> bool:
    path = config_file or config_file_path()
    if not path.is_file():
        return False
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(loaded, dict):
        return False
    return loaded.get(DISMISSAL_KEY) is True


def remember_offer_dismissed(*, config_file: Path | None = None) -> bool:
    """Record Not now in the existing config file. This is not a configured flag."""

    path = config_file or config_file_path()
    merged = merge_config_settings_atomic(
        config_dir=path.parent,
        config_file=path,
        defaults={},
        updates={DISMISSAL_KEY: True},
        removed_keys=set(),
        logger=logger,
    )
    return merged is not None


def terminal_hint_for_request(*, reactive_input: bool = False, power_controls: bool = False) -> str:
    from keyrgb.gui.hardware_access import HardwareAccessRequest

    return terminal_command(HardwareAccessRequest(reactive_input=reactive_input, power_controls=power_controls))
