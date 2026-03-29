from __future__ import annotations

from src.core.effects.catalog import resolve_effect_name_for_backend


def test_resolve_effect_name_preserves_backend_exposed_hardware_effect() -> None:
    class _Backend:
        def effects(self):
            return {"wave": object()}

    assert resolve_effect_name_for_backend("wave", _Backend()) == "wave"


def test_resolve_effect_name_prefers_software_collision_without_hw_prefix() -> None:
    class _Backend:
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

    assert resolve_effect_name_for_backend("hw:wave", _Backend()) == "wave"