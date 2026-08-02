from __future__ import annotations

from types import SimpleNamespace

from src.core.backends.base import (
    DEFAULT_BACKEND_CAPABILITIES,
    BackendCapabilities,
    normalize_backend_capabilities,
)


def test_normalize_backend_capabilities_defaults_missing_value_to_supported() -> None:
    assert normalize_backend_capabilities(None) == DEFAULT_BACKEND_CAPABILITIES


def test_normalize_backend_capabilities_preserves_typed_snapshot() -> None:
    caps = BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=True)

    assert normalize_backend_capabilities(caps) is caps


def test_normalize_backend_capabilities_reads_partial_object_with_field_defaults() -> None:
    caps = normalize_backend_capabilities(SimpleNamespace(per_key=False, color=False))

    assert caps == BackendCapabilities(
        per_key=False,
        color=False,
        hardware_effects=True,
        palette=True,
    )


def test_normalize_backend_capabilities_honors_custom_default() -> None:
    fallback = BackendCapabilities(per_key=False, color=False, hardware_effects=False, palette=False)

    assert normalize_backend_capabilities(SimpleNamespace(color=True), default=fallback) == BackendCapabilities(
        per_key=False,
        color=True,
        hardware_effects=False,
        palette=False,
    )
