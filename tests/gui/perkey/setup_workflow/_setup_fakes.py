"""Shared fakes for the guided-setup workflow unit tests.

Split out of ``test_setup_integration_unit.py`` to keep test modules under
the LOC gate. No behavior lives here: headless editor/config/profiles and
hardware doubles plus the tray-snapshot helpers every setup test reuses.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.profile import profiles as real_profiles
from keyrgb.gui.perkey.setup_workflow import integration
from keyrgb.gui.perkey.setup_workflow.integration import (
    GuidedSetupController,
    capture_setup_source,
    resolve_setup_preflight,
)
from keyrgb.gui.perkey.setup_workflow.model import draft_from_source
from keyrgb.tray.ui.gui_launch import build_perkey_preflight_payload

ROWS, COLS = 4, 6
VALID_KEYMAP = {"a": [[0, 0]], "b": [[1, 2]]}
OTHER_KEYMAP = {"a": [[0, 1]], "c": [[3, 5]]}


def _per_key_caps() -> BackendCapabilities:
    return BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=False, palette=False)


def _brightness_only_caps() -> BackendCapabilities:
    return BackendCapabilities(brightness=False, per_key=False, color=False, hardware_effects=False, palette=False)


def _snapshot_env(*, per_key: bool, tray_managed: bool = True) -> dict[str, str]:
    caps = _per_key_caps() if per_key else _brightness_only_caps()
    payload = build_perkey_preflight_payload(backend_caps=caps, backend_name="Fake Backend", dimensions=(ROWS, COLS))
    env: dict[str, str] = {integration.PREFLIGHT_ENV_VAR: json.dumps(payload, sort_keys=True)}
    if tray_managed:
        env[integration.TRAY_MANAGED_ENV_VAR] = "1"
    return env


class FakeVar:
    def __init__(self, value: object = "") -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value


class FakeCanvas:
    def __init__(self) -> None:
        self.redraws = 0

    def redraw(self) -> None:
        self.redraws += 1


class FakeOverlayControls:
    def __init__(self) -> None:
        self.syncs = 0

    def sync_vars_from_scope(self) -> None:
        self.syncs += 1


class FakeConfig:
    def __init__(self, base_dir: Path) -> None:
        self.CONFIG_DIR = base_dir / "keyrgb"
        self.CONFIG_FILE = self.CONFIG_DIR / "config.json"
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.physical_layout = "ansi"
        self.layout_legend_pack = "auto"
        self.batches = 0
        self.assignments: list[tuple[str, object]] = []

    def __setattr__(self, name: str, value: object) -> None:
        object.__setattr__(self, name, value)

    @contextmanager
    def batch_update(self) -> Iterator[FakeConfig]:
        self.batches += 1
        yield self


class FakeKb:
    def __init__(self, *, with_writer: bool = True) -> None:
        if with_writer:
            self.set_key_colors = lambda *args, **kwargs: None  # type: ignore[attr-defined]


class FakeBackend:
    def __init__(self, *, per_key: bool = True) -> None:
        self._per_key = per_key
        self.name = "Fake Backend"

    def capabilities(self) -> BackendCapabilities:
        return (
            BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=False, palette=False)
            if self._per_key
            else _brightness_only_caps()
        )

    def dimensions(self) -> tuple[int, int]:
        return (ROWS, COLS)


class FakeHardwareModule:
    def __init__(self, backend: FakeBackend | None) -> None:
        self._backend = backend


class FakeEditor:
    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self._physical_layout = "ansi"
        self._layout_legend_pack = "auto"
        self.profile_name = "default"
        self.layout_slot_overrides: dict[str, dict[str, object]] = {}
        self.keymap: dict[str, object] = dict(VALID_KEYMAP)
        self.layout_tweaks: dict[str, float] = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = {}
        self.kb: FakeKb | None = None
        self._layout_var = FakeVar("ansi")
        self._legend_pack_var = FakeVar("auto")
        self.canvas = FakeCanvas()
        self.overlay_controls = FakeOverlayControls()
        self.slot_control_refreshes = 0
        self.visible_syncs = 0
        self.commits = 0

    def _normalize_layout_legend_pack(self, layout_id: str, legend_pack_id: str | None) -> str:
        _ = layout_id
        return str(legend_pack_id or "auto")

    def _refresh_layout_slot_controls(self) -> None:
        self.slot_control_refreshes += 1

    def _sync_visible_layout_state(self) -> None:
        self.visible_syncs += 1

    def _commit(self, *, force: bool = False) -> None:
        _ = force
        self.commits += 1


class FakeProfiles:
    """Recording profiles double; normalization delegates to the real APIs."""

    def __init__(self, *, fail_on: str | None = None, fail_times: int = 1) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.fail_on = fail_on
        self.fail_remaining = fail_times

    def _maybe_fail(self, stage: str) -> None:
        if self.fail_on == stage and self.fail_remaining > 0:
            self.fail_remaining -= 1
            raise OSError(f"fake {stage} failure")

    def normalize_keymap(self, raw: object, *, physical_layout: str | None) -> Any:
        return real_profiles.normalize_keymap(raw, physical_layout=physical_layout)

    def normalize_layout_per_key_tweaks(self, raw: object, *, physical_layout: str | None) -> Any:
        return real_profiles.normalize_layout_per_key_tweaks(raw, physical_layout=physical_layout)

    def normalize_layout_slot_overrides(self, raw: object, *, physical_layout: str | None) -> Any:
        return real_profiles.normalize_layout_slot_overrides(raw, physical_layout=physical_layout)

    def save_keymap(self, keymap: Any, name: Any = None, *, physical_layout: str | None = None) -> None:
        self.calls.append(("save_keymap", dict(keymap), name, physical_layout))
        self._maybe_fail("save_keymap")

    def save_layout_global(self, tweaks: Any, name: Any = None) -> None:
        self.calls.append(("save_layout_global", dict(tweaks), name))
        self._maybe_fail("save_layout_global")

    def save_layout_per_key(self, per_key: Any, name: Any = None) -> None:
        self.calls.append(("save_layout_per_key", dict(per_key), name))

    def save_layout_slots(self, slots: Any, name: Any = None, *, physical_layout: str | None = None) -> None:
        self.calls.append(("save_layout_slots", dict(slots), name, physical_layout))


def _make_controller(
    editor: FakeEditor,
    profiles: FakeProfiles,
    *,
    env: Mapping[str, str],
    hardware_module: FakeHardwareModule | None = None,
) -> GuidedSetupController:
    _ = profiles
    draft = draft_from_source(capture_setup_source(editor))
    preflight = resolve_setup_preflight(editor, env=dict(env), hardware_module=hardware_module)
    return GuidedSetupController(draft=draft, preflight=preflight, rows=preflight.rows, cols=preflight.cols)
