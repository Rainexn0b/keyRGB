"""UX-04 guided setup integration: shared protocols, constants, and step types.

Tk-free home for the narrow guided-setup boundary vocabulary: environment
markers, expected-exception tuples, editor/hardware/profiles protocols, the
ordered :class:`SetupStep` flow, and the parsed tray snapshot view. None of
the helpers here probe hardware or touch profiles/config.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

PREFLIGHT_ENV_VAR = "KEYRGB_PERKEY_PREFLIGHT"
TRAY_MANAGED_ENV_VAR = "KEYRGB_TRAY_MANAGED_GUI"

_EXPECTED_EVIDENCE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_EXPECTED_CONFIG_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_EXPECTED_SESSION_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

_MIN_DIMENSION = 1
_MAX_DIMENSION = 64

_OVERLAY_TWEAK_DEFAULTS: dict[str, float] = {
    "dx": 0.0,
    "dy": 0.0,
    "sx": 1.0,
    "sy": 1.0,
    "inset": 0.06,
}
_OVERLAY_INSET_MIN = 0.0
_OVERLAY_INSET_MAX = 0.20

_SESSION_FILE_NAME = "guided-session.json"
_SESSION_TMP_PREFIX = "keyrgb-guided-setup-"


class _SetupVarProtocol(Protocol):
    def get(self) -> object: ...

    def set(self, value: object) -> None: ...


class _SetupCanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _SetupOverlayControlsProtocol(Protocol):
    def sync_vars_from_scope(self) -> None: ...


class _SetupConfigProtocol(Protocol):
    CONFIG_FILE: object
    CONFIG_DIR: object
    physical_layout: str
    layout_legend_pack: str

    def batch_update(self) -> AbstractContextManager[object]: ...


class _SetupEditorProtocol(Protocol):  # noqa: PYI046 - boundary protocol consumed by evidence/commit siblings
    _physical_layout: str
    _layout_legend_pack: str
    profile_name: str
    layout_slot_overrides: dict[str, dict[str, object]]
    keymap: dict[str, object]
    layout_tweaks: dict[str, float]
    per_key_layout_tweaks: dict[str, dict[str, float]]
    config: _SetupConfigProtocol
    kb: object | None
    canvas: _SetupCanvasProtocol
    overlay_controls: _SetupOverlayControlsProtocol
    _layout_var: _SetupVarProtocol
    _legend_pack_var: _SetupVarProtocol

    def _normalize_layout_legend_pack(self, layout_id: str, legend_pack_id: str | None) -> str: ...

    def _refresh_layout_slot_controls(self) -> None: ...

    def _sync_visible_layout_state(self) -> None: ...

    def _commit(self, *, force: bool) -> None: ...


class _SetupHardwareModule(Protocol):  # noqa: PYI046 - boundary protocol consumed by the preflight sibling
    _backend: object | None


class _SetupBackendProtocol(Protocol):  # noqa: PYI046 - boundary protocol consumed by the preflight sibling
    name: object

    def capabilities(self) -> object: ...

    def dimensions(self) -> object: ...


KeyCells = tuple[tuple[int, int], ...]


class _ProfilesModule(Protocol):  # noqa: PYI046 - boundary protocol consumed by the commit sibling
    def normalize_keymap(self, raw: object, *, physical_layout: str | None) -> dict[str, KeyCells]: ...

    def normalize_layout_per_key_tweaks(
        self, raw: object, *, physical_layout: str | None
    ) -> dict[str, dict[str, float]]: ...

    def normalize_layout_slot_overrides(
        self, raw: object, *, physical_layout: str | None
    ) -> dict[str, dict[str, object]]: ...

    def save_keymap(self, keymap: dict[str, KeyCells], name: str | None, *, physical_layout: str | None) -> None: ...

    def save_layout_global(self, tweaks: dict[str, float], name: str | None) -> None: ...

    def save_layout_per_key(self, per_key: dict[str, dict[str, float]], name: str | None) -> None: ...

    def save_layout_slots(
        self, slots: dict[str, dict[str, object]], name: str | None, *, physical_layout: str | None
    ) -> dict[str, dict[str, object]]: ...


class SetupStep(str, Enum):
    """Ordered guided wizard steps; overlay stays optional/skippable."""

    PREFLIGHT = "preflight"
    LAYOUT = "layout"
    OPTIONAL_KEYS = "optional_keys"
    CALIBRATION = "calibration"
    OVERLAY = "overlay"
    REVIEW = "review"


SETUP_STEPS: tuple[SetupStep, ...] = (
    SetupStep.PREFLIGHT,
    SetupStep.LAYOUT,
    SetupStep.OPTIONAL_KEYS,
    SetupStep.CALIBRATION,
    SetupStep.OVERLAY,
    SetupStep.REVIEW,
)


@dataclass(frozen=True)
class _SnapshotView:
    """Parsed tray preflight snapshot; absent when no usable JSON exists."""

    present: bool
    capabilities: dict[str, bool] | None = None
    backend_name: str | None = None
    dimensions: tuple[int, int] | None = None


def _validated_dimensions(value: object) -> tuple[int, int] | None:
    pair: object = tuple(value) if isinstance(value, list) else value
    if (
        isinstance(pair, tuple)
        and len(pair) == 2
        and all(type(item) is int for item in pair)
        and all(_MIN_DIMENSION <= item <= _MAX_DIMENSION for item in pair)
    ):
        rows, cols = pair
        return int(rows), int(cols)
    return None
