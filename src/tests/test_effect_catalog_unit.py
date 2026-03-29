from __future__ import annotations

from src.core.effects.catalog import resolve_effect_name_for_backend


def test_resolve_effect_name_preserves_backend_exposed_hardware_effect() -> None:
    class _Backend:
        def effects(self):
            return {"wave": object()}

    assert resolve_effect_name_for_backend("wave", _Backend()) == "wave"


def test_resolve_effect_name_migrates_legacy_rainbow_without_backend_support() -> None:
    class _Backend:
        def effects(self):
            return {}

    assert resolve_effect_name_for_backend("rainbow", _Backend()) == "rainbow_wave"


def test_resolve_effect_name_drops_unsupported_legacy_hw_name_without_backend_support() -> None:
    class _Backend:
        def effects(self):
            return {}

    assert resolve_effect_name_for_backend("wave", _Backend()) == "none"