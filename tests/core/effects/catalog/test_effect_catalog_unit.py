from __future__ import annotations

import pytest

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.effects.catalog import (
    detected_backend_hw_effect_names,
    hardware_effect_selection_key,
    normalize_effect_name,
    resolve_effect_name_for_backend,
)


class _HardwareEffectsBackend:
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            brightness=True,
            per_key=False,
            color=True,
            hardware_effects=True,
            palette=False,
        )


def test_resolve_effect_name_preserves_backend_exposed_hardware_effect() -> None:
    class _Backend(_HardwareEffectsBackend):
        def effects(self):
            return {"wave": object()}

    assert resolve_effect_name_for_backend("wave", _Backend()) == "wave"


def test_legacy_breathing_sw_alias_normalizes_to_software_breathing() -> None:
    assert normalize_effect_name("breathing_sw") == "breathing"


def test_firmware_collision_uses_hw_prefix_for_software_breathing() -> None:
    assert hardware_effect_selection_key("breathing") == "hw:breathing"


def test_resolve_effect_name_prefers_software_collision_without_hw_prefix() -> None:
    class _Backend(_HardwareEffectsBackend):
        def effects(self):
            return {"spectrum_cycle": object()}

    assert resolve_effect_name_for_backend("spectrum_cycle", _Backend()) == "spectrum_cycle"


def test_resolve_effect_name_migrates_legacy_rainbow_without_backend_support() -> None:
    class _Backend:
        def effects(self):
            return {}

    assert resolve_effect_name_for_backend("rainbow", _Backend()) == "rainbow"


def test_resolve_effect_name_preserves_forced_hw_name_for_later_runtime_validation() -> None:
    class _Backend:
        def effects(self):
            return {}

    assert resolve_effect_name_for_backend("hw:wave", _Backend()) == "none"


def test_effect_method_cannot_replace_missing_capability_evidence() -> None:
    class _Backend:
        def effects(self):
            return {"wave": object()}

    assert detected_backend_hw_effect_names(_Backend()) == ()


def test_resolve_effect_name_falls_back_when_backend_effect_lookup_raises_runtime_error() -> None:
    class _Backend(_HardwareEffectsBackend):
        def effects(self):
            raise RuntimeError("effect lookup failed")

    assert resolve_effect_name_for_backend("wave", _Backend()) == "wave"


def test_resolve_effect_name_propagates_unexpected_backend_effect_lookup_failures() -> None:
    class _Backend(_HardwareEffectsBackend):
        def effects(self):
            raise AssertionError("unexpected effect lookup bug")

    with pytest.raises(AssertionError, match="unexpected effect lookup bug"):
        resolve_effect_name_for_backend("wave", _Backend())
