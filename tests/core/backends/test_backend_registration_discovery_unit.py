from __future__ import annotations

from keyrgb.core.backends.base import BackendMetadata, BackendRegistration, BackendRole, BackendStability
from keyrgb.core.backends.registry import (
    _invalidate_discovery_cache,
    discover_backend_registrations,
    get_metadata_for_backend_name,
    iter_auxiliary_specs,
    iter_backends,
)


def test_builtin_primary_backends_are_discovered_from_package_markers() -> None:
    _invalidate_discovery_cache()
    names = {reg.metadata.name for reg in discover_backend_registrations() if reg.metadata.role is BackendRole.PRIMARY}

    assert "sysfs-leds" in names
    assert "asusctl-aura" in names
    assert "ite8291r3_perkey" in names
    assert "sysfs-mouse" not in names


def test_auxiliary_sysfs_mouse_is_excluded_from_primary_specs_but_constructable() -> None:
    _invalidate_discovery_cache()
    auxiliary = iter_auxiliary_specs()

    assert [spec.name for spec in auxiliary] == ["sysfs-mouse"]
    backends = iter_backends(specs=auxiliary)
    assert [backend.name for backend in backends] == ["sysfs-mouse"]


def test_metadata_drives_provider_tier_and_safety() -> None:
    _invalidate_discovery_cache()
    sysfs = get_metadata_for_backend_name("sysfs-leds")
    ite = get_metadata_for_backend_name("ite8291r3_perkey")
    mouse = get_metadata_for_backend_name("sysfs-mouse")

    assert sysfs is not None
    assert sysfs.provider == "kernel-sysfs"
    assert sysfs.diagnostics_tier() == 1
    assert sysfs.auto_safety_tier() == 1
    assert sysfs.stability is BackendStability.VALIDATED

    assert ite is not None
    assert ite.provider == "usb-userspace"
    assert ite.diagnostics_tier() == 2
    assert ite.auto_safety_tier() == 0

    assert mouse is not None
    assert mouse.role is BackendRole.AUXILIARY
    assert mouse.provider == "kernel-sysfs"


def test_registration_marker_can_be_transformed_without_registry_edits() -> None:
    class _SyntheticBackend:
        name = "synthetic-primary"
        priority = 1

        def __init__(self) -> None:
            pass

    registration = BackendRegistration(
        metadata=BackendMetadata(name="synthetic-primary", priority=7, provider="kernel-sysfs"),
        factory=_SyntheticBackend,
    )

    assert registration.metadata.auto_safety_tier() == 1
    assert registration.factory is _SyntheticBackend
    assert registration.factory().name == "synthetic-primary"
