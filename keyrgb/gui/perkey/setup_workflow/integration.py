"""UX-04 modal guided setup integration (Tk-free).

Glue between the pure setup core (``model``/``preflight``/``transaction``)
and the thin Tk modal (``wizard``). Preflight evidence comes only from the
``KEYRGB_PERKEY_PREFLIGHT`` snapshot or the already-selected backend/open
``kb`` (never probing); live preview stands only when the tray-managed
snapshot declares ``per_key``. Temp session helpers reuse the guided
session schema; the commit adapter writes config plus the existing
profile's setup payloads only, with hardware apply solely through
``editor._commit(force=True)`` (omitted config-only). Only the narrow
``OSError``/``RuntimeError``/``TypeError``/``ValueError``/``AttributeError``
boundary is caught; unexpected exceptions propagate.

This module is the stable public facade; the implementation lives in the
``integration_parts`` subpackage (``integration_types`` for
protocols/constants, ``integration_evidence`` for cached-only preflight
evidence, ``integration_preflight`` for the preflight gate,
``integration_session`` for temp guided sessions, ``integration_commit``
for the commit adapter, and ``integration_controller`` for the Tk-free
controller). Every name previously available here is re-exported unchanged
so existing importers, ``__all__`` consumers, and monkeypatch seams keep
working.
"""

from __future__ import annotations

import logging

from . import model as _model_module
from .integration_parts import (
    integration_commit as _commit_module,
    integration_controller as _controller_module,
    integration_evidence as _evidence_module,
    integration_preflight as _preflight_module,
    integration_session as _session_module,
    integration_types as _types_module,
)

__all__ = [
    "PREFLIGHT_ENV_VAR",
    "SETUP_STEPS",
    "TRAY_MANAGED_ENV_VAR",
    "GuidedSetupController",
    "SetupStep",
    "adopt_guided_result",
    "available_layouts",
    "build_setup_commit_callbacks",
    "calibration_skip_validation",
    "capture_setup_source",
    "cleanup_guided_session",
    "collect_preflight_evidence",
    "config_is_writable",
    "create_guided_session_file",
    "draft_from_source",
    "is_tray_managed",
    "legend_pack_choices",
    "optional_slot_states",
    "read_guided_result",
    "resolve_setup_preflight",
    "snapshot_declares_per_key",
]

logger = logging.getLogger(__name__)

PREFLIGHT_ENV_VAR = _types_module.PREFLIGHT_ENV_VAR
SETUP_STEPS = _types_module.SETUP_STEPS
TRAY_MANAGED_ENV_VAR = _types_module.TRAY_MANAGED_ENV_VAR
GuidedSetupController = _controller_module.GuidedSetupController
SetupStep = _types_module.SetupStep
adopt_guided_result = _session_module.adopt_guided_result
available_layouts = _evidence_module.available_layouts
build_setup_commit_callbacks = _commit_module.build_setup_commit_callbacks
calibration_skip_validation = _preflight_module.calibration_skip_validation
capture_setup_source = _evidence_module.capture_setup_source
cleanup_guided_session = _session_module.cleanup_guided_session
collect_preflight_evidence = _preflight_module.collect_preflight_evidence
config_is_writable = _evidence_module.config_is_writable
create_guided_session_file = _session_module.create_guided_session_file
draft_from_source = _model_module.draft_from_source
is_tray_managed = _evidence_module.is_tray_managed
legend_pack_choices = _evidence_module.legend_pack_choices
optional_slot_states = _evidence_module.optional_slot_states
read_guided_result = _session_module.read_guided_result
resolve_setup_preflight = _preflight_module.resolve_setup_preflight
snapshot_declares_per_key = _evidence_module.snapshot_declares_per_key

_EXPECTED_CONFIG_ERRORS = _types_module._EXPECTED_CONFIG_ERRORS
_EXPECTED_EVIDENCE_ERRORS = _types_module._EXPECTED_EVIDENCE_ERRORS
_EXPECTED_SESSION_ERRORS = _types_module._EXPECTED_SESSION_ERRORS
_MIN_DIMENSION = _types_module._MIN_DIMENSION
_MAX_DIMENSION = _types_module._MAX_DIMENSION
_OVERLAY_TWEAK_DEFAULTS = _types_module._OVERLAY_TWEAK_DEFAULTS
_OVERLAY_INSET_MIN = _types_module._OVERLAY_INSET_MIN
_OVERLAY_INSET_MAX = _types_module._OVERLAY_INSET_MAX
_SESSION_FILE_NAME = _types_module._SESSION_FILE_NAME
_SESSION_TMP_PREFIX = _types_module._SESSION_TMP_PREFIX
_SnapshotView = _types_module._SnapshotView
_SetupBackendProtocol = _types_module._SetupBackendProtocol
_SetupCanvasProtocol = _types_module._SetupCanvasProtocol
_SetupConfigProtocol = _types_module._SetupConfigProtocol
_SetupEditorProtocol = _types_module._SetupEditorProtocol
_SetupHardwareModule = _types_module._SetupHardwareModule
_SetupOverlayControlsProtocol = _types_module._SetupOverlayControlsProtocol
_SetupVarProtocol = _types_module._SetupVarProtocol
_ProfilesModule = _types_module._ProfilesModule
KeyCells = _types_module.KeyCells
_validated_dimensions = _types_module._validated_dimensions
_safe_str = _evidence_module._safe_str
_safe_mapping = _evidence_module._safe_mapping
_safe_float_mapping = _evidence_module._safe_float_mapping
_safe_override_mapping = _evidence_module._safe_override_mapping
_safe_per_key_mapping = _evidence_module._safe_per_key_mapping
_parse_snapshot_view = _evidence_module._parse_snapshot_view
_backend_fallback_evidence = _preflight_module._backend_fallback_evidence
_guided_result_version = _session_module._guided_result_version
_default_profiles_module = _commit_module._default_profiles_module
_apply_fields_to_editor = _commit_module._apply_fields_to_editor
_sync_editor_ui = _commit_module._sync_editor_ui
_persist_fields = _commit_module._persist_fields
_editor_profile_name = _commit_module._editor_profile_name
