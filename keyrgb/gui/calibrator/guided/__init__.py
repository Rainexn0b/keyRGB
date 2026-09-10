"""Guided calibrator surface: session protocol/storage plus preview journal.

Public names are re-exported here so ``keyrgb.gui.calibrator.app``, the
per-key setup workflow, and preview helpers share one compact import surface.
"""

from __future__ import annotations

from . import (
    config_view as _config_view,
    journal_model as _journal_model,
    journal_recovery as _journal_recovery,
    journal_store as _journal_store,
    session_protocol as _session_protocol,
    session_storage as _session_storage,
)

CALIBRATOR_USAGE = _session_protocol.CALIBRATOR_USAGE
GUIDED_SESSION_FLAG = _session_protocol.GUIDED_SESSION_FLAG
GUIDED_SESSION_RESULT_VERSION = _session_protocol.GUIDED_SESSION_RESULT_VERSION
PREVIEW_JOURNAL_FILENAME = _journal_model.PREVIEW_JOURNAL_FILENAME
PREVIEW_JOURNAL_VERSION = _journal_model.PREVIEW_JOURNAL_VERSION
_SAVE_AND_CLOSE_BUTTON_TEXT = _session_protocol._SAVE_AND_CLOSE_BUTTON_TEXT
_SAVE_BUTTON_TEXT = _session_protocol._SAVE_BUTTON_TEXT
_encode_keymap_payload = _session_storage._encode_keymap_payload
GuidedConfigView = _config_view.GuidedConfigView
GuidedSession = _session_protocol.GuidedSession
GuidedSessionError = _session_protocol.GuidedSessionError
GuidedSessionHelpRequested = _session_protocol.GuidedSessionHelpRequested
PreviewConfigProtocol = _journal_model.PreviewConfigProtocol
PreviewSnapshot = _journal_model.PreviewSnapshot
apply_snapshot_to_config = _journal_recovery.apply_snapshot_to_config
clear_preview_journal = _journal_store.clear_preview_journal
config_dir_of = _journal_store.config_dir_of
encode_guided_result_keymap = _session_storage.encode_guided_result_keymap
guided_session_path_of = _config_view.guided_session_path_of
journal_path = _journal_store.journal_path
journal_snapshot_fields = _journal_model.journal_snapshot_fields
load_guided_session = _session_storage.load_guided_session
load_preview_snapshot = _journal_store.load_preview_snapshot
parse_guided_session_argv = _session_protocol.parse_guided_session_argv
recover_stale_preview_journal = _journal_recovery.recover_stale_preview_journal
snapshot_preview_state = _journal_store.snapshot_preview_state
validate_journal_payload = _journal_model.validate_journal_payload
write_guided_result = _session_storage.write_guided_result
write_preview_journal = _journal_store.write_preview_journal

__all__ = [
    "CALIBRATOR_USAGE",
    "GUIDED_SESSION_FLAG",
    "GUIDED_SESSION_RESULT_VERSION",
    "PREVIEW_JOURNAL_FILENAME",
    "PREVIEW_JOURNAL_VERSION",
    "GuidedConfigView",
    "GuidedSession",
    "GuidedSessionError",
    "GuidedSessionHelpRequested",
    "PreviewConfigProtocol",
    "PreviewSnapshot",
    "apply_snapshot_to_config",
    "clear_preview_journal",
    "config_dir_of",
    "encode_guided_result_keymap",
    "guided_session_path_of",
    "journal_path",
    "journal_snapshot_fields",
    "load_guided_session",
    "load_preview_snapshot",
    "parse_guided_session_argv",
    "recover_stale_preview_journal",
    "snapshot_preview_state",
    "validate_journal_payload",
    "write_guided_result",
    "write_preview_journal",
]
