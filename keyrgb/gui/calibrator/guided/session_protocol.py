"""Guided-session protocol: flags, payload type, and argv parsing.

Standalone behavior (``keyrgb-calibrate`` with no flags) is unchanged: the
calibrator loads/saves ``profiles/<name>/keymap.json`` with ``Save`` /
``Save && Close`` copy.  A parent tool may instead launch::

    python -m keyrgb.gui.calibrator --guided-session /tmp/xyz-session.json

No USB/device acquisition happens here; preview and restoration stay
Config-mediated exactly like standalone mode.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

GUIDED_SESSION_FLAG = "--guided-session"
GUIDED_SESSION_RESULT_VERSION = 1

CALIBRATOR_USAGE = """usage: keyrgb-calibrate [--guided-session PATH] [-h | --help]

  (no flags)               standalone calibration; saves to profiles/<name>/keymap.json
  --guided-session PATH    guided session: initialize from PATH, write the
                           normalized keymap result back to PATH ("Use Result")
  -h, --help               show this help and exit"""

_HELP_FLAGS = ("-h", "--help")

_SAVE_BUTTON_TEXT = "Use Result"
_SAVE_AND_CLOSE_BUTTON_TEXT = "Use Result && Close"


class GuidedSessionError(ValueError):
    """Raised when a guided-session path or payload is unusable.

    Subclasses ``ValueError`` so misconfiguration-style failures stay
    distinguishable from unexpected runtime faults; callers surface the
    message and exit non-zero without mutating profile data.
    """


class GuidedSessionHelpRequested(Exception):
    """Control-flow signal: ``-h``/``--help`` was requested.

    Caught immediately in :func:`main`, which prints usage and exits 0.
    Never escapes the calibrator entrypoint.
    """


@dataclass
class GuidedSession:
    """Validated guided-session payload plus its source path."""

    source_path: Path
    num_rows: int = 0
    num_cols: int = 0
    physical_layout: str = "auto"
    legend_pack: str | None = None
    slot_overrides: dict[str, dict[str, object]] = field(default_factory=dict)
    keymap: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    layout_tweaks: dict[str, float] = field(default_factory=dict)
    per_key_layout_tweaks: dict[str, dict[str, float]] = field(default_factory=dict)


def parse_guided_session_argv(argv: Sequence[str] | None = None) -> Path | None:
    """Return the ``--guided-session PATH`` value, or ``None`` for standalone mode.

    ``argv`` defaults to ``sys.argv[1:]``.  Both ``--guided-session PATH``
    and ``--guided-session=PATH`` spellings are accepted.  ``-h``/``--help``
    raises :class:`GuidedSessionHelpRequested`.  Any other flag, a missing
    value, or an empty path raises :class:`GuidedSessionError`.
    """

    args = list(sys.argv[1:] if argv is None else argv)
    if any(arg in _HELP_FLAGS for arg in args):
        raise GuidedSessionHelpRequested(CALIBRATOR_USAGE)
    session_value: str | None = None
    for index, arg in enumerate(args):
        if arg == GUIDED_SESSION_FLAG:
            if session_value is not None:
                raise GuidedSessionError(f"duplicate {GUIDED_SESSION_FLAG} flag")
            if index + 1 >= len(args):
                raise GuidedSessionError(f"{GUIDED_SESSION_FLAG} requires a session file path")
            session_value = args[index + 1]
        elif arg.startswith(f"{GUIDED_SESSION_FLAG}="):
            if session_value is not None:
                raise GuidedSessionError(f"duplicate {GUIDED_SESSION_FLAG} flag")
            session_value = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            raise GuidedSessionError(f"unknown option for keyrgb-calibrate: {arg!r}")
        elif index > 0 and args[index - 1] == GUIDED_SESSION_FLAG:
            continue
        else:
            raise GuidedSessionError(f"unexpected positional argument for keyrgb-calibrate: {arg!r}")

    if session_value is None:
        return None
    if not session_value.strip():
        raise GuidedSessionError(f"{GUIDED_SESSION_FLAG} requires a non-empty session file path")
    return Path(session_value).expanduser()
