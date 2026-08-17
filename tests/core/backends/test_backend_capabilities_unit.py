from __future__ import annotations

from types import SimpleNamespace

from src.core.backends.base import (
    DEFAULT_BACKEND_CAPABILITIES,
    BackendCapabilities,
    normalize_backend_capabilities,
    supports_per_key_output,
)
from src.core.effects.device import NullKeyboard


def test_normalize_backend_capabilities_defaults_missing_value_to_unsupported() -> None:
    assert normalize_backend_capabilities(None) == DEFAULT_BACKEND_CAPABILITIES
    assert DEFAULT_BACKEND_CAPABILITIES == BackendCapabilities(
        brightness=False,
        per_key=False,
        color=False,
        hardware_effects=False,
        palette=False,
    )


def test_normalize_backend_capabilities_preserves_typed_snapshot() -> None:
    caps = BackendCapabilities(brightness=True, per_key=False, color=True, hardware_effects=False, palette=True)

    assert normalize_backend_capabilities(caps) is caps


def test_normalize_backend_capabilities_reads_partial_object_with_field_defaults() -> None:
    caps = normalize_backend_capabilities(SimpleNamespace(per_key=False, color=False))

    assert caps == BackendCapabilities(
        brightness=False,
        per_key=False,
        color=False,
        hardware_effects=False,
        palette=False,
    )


def test_normalize_backend_capabilities_honors_custom_default() -> None:
    fallback = BackendCapabilities(
        brightness=False,
        per_key=False,
        color=False,
        hardware_effects=False,
        palette=False,
    )

    assert normalize_backend_capabilities(SimpleNamespace(color=True), default=fallback) == BackendCapabilities(
        brightness=False,
        per_key=False,
        color=True,
        hardware_effects=False,
        palette=False,
    )


def test_method_presence_cannot_replace_per_key_capability_evidence() -> None:
    device = NullKeyboard()

    assert supports_per_key_output(DEFAULT_BACKEND_CAPABILITIES, device) is False
    assert (
        supports_per_key_output(
            BackendCapabilities(
                brightness=True,
                per_key=True,
                color=True,
                hardware_effects=False,
                palette=False,
            ),
            device,
        )
        is True
    )
