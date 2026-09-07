from __future__ import annotations

from dataclasses import dataclass

import pytest

from keyrgb.core.backends.base import (
    BackendMetadata,
    BackendRegistration,
    BackendStability,
    ExperimentalEvidence,
    ProbeResult,
    normalize_backend_stability,
    normalize_experimental_evidence,
)
from keyrgb.core.backends.policies.backend_selection import (
    experimental_backends_enabled,
    experimental_evidence_for_backend,
    experimental_evidence_label,
)
from keyrgb.core.backends.registry import (
    BackendSpec,
    _probe_backend,
    _spec_from_registration,
    iter_backends,
)


@dataclass
class DummyBackend:
    name: str
    priority: int
    available: bool
    confidence: int = 50
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: ExperimentalEvidence | None = None

    def is_available(self) -> bool:
        return self.available

    def probe(self) -> ProbeResult:
        return ProbeResult(available=self.available, reason="test", confidence=int(self.confidence))

    def capabilities(self):
        raise NotImplementedError

    def get_device(self):
        raise NotImplementedError

    def dimensions(self):
        raise NotImplementedError

    def effects(self):
        raise NotImplementedError

    def colors(self):
        raise NotImplementedError


class _BrokenStrValue:
    def __str__(self) -> str:
        raise AssertionError("unexpected stringification")


def test_spec_from_registration_reads_metadata_without_constructing_factory() -> None:
    class ConstructionGuardFactory:
        def __call__(self) -> None:
            raise AssertionError("backend must remain lazy")

    reg = BackendRegistration(
        metadata=BackendMetadata(name="construction-guard", priority=42),
        factory=ConstructionGuardFactory(),
    )

    spec = _spec_from_registration(reg)

    assert spec.name == "construction-guard"
    assert spec.priority == 42
    assert spec.factory is reg.factory


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BackendStability.EXPERIMENTAL, BackendStability.EXPERIMENTAL),
        ("DoRmAnT", BackendStability.DORMANT),
    ],
)
def test_normalize_backend_stability_accepts_enums_and_strings(
    value: object,
    expected: BackendStability,
) -> None:
    assert normalize_backend_stability(value) is expected


@pytest.mark.parametrize("value", [None, "unknown", 42, _BrokenStrValue()])
def test_normalize_backend_stability_falls_back_for_invalid_or_non_string_values(value: object) -> None:
    assert normalize_backend_stability(value) is BackendStability.VALIDATED


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (ExperimentalEvidence.REVERSE_ENGINEERED, ExperimentalEvidence.REVERSE_ENGINEERED),
        ("SpEcUlAtIvE", ExperimentalEvidence.SPECULATIVE),
    ],
)
def test_normalize_experimental_evidence_accepts_enums_and_strings(
    value: object,
    expected: ExperimentalEvidence,
) -> None:
    assert normalize_experimental_evidence(value) is expected


@pytest.mark.parametrize("value", [None, "unknown", 42, _BrokenStrValue()])
def test_normalize_experimental_evidence_falls_back_for_invalid_or_non_string_values(value: object) -> None:
    assert normalize_experimental_evidence(value) is None


def test_experimental_evidence_helper_normalizes_backend_metadata() -> None:
    backend = DummyBackend(
        "ite8910_perkey",
        100,
        True,
        confidence=90,
        stability=BackendStability.EXPERIMENTAL,
        experimental_evidence=ExperimentalEvidence.REVERSE_ENGINEERED,
    )

    assert experimental_evidence_for_backend(backend) == ExperimentalEvidence.REVERSE_ENGINEERED


def test_experimental_evidence_label_uses_user_facing_wording() -> None:
    assert experimental_evidence_label(ExperimentalEvidence.REVERSE_ENGINEERED) == "research-backed"
    assert experimental_evidence_label(ExperimentalEvidence.SPECULATIVE) == "speculative"


def test_experimental_backends_enabled_returns_false_when_config_read_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    class BrokenConfig:
        @property
        def experimental_backends_enabled(self) -> bool:
            raise RuntimeError("config boom")

    monkeypatch.setattr("keyrgb.core.config.Config", BrokenConfig)

    assert experimental_backends_enabled() is False


def test_experimental_backends_enabled_propagates_unexpected_config_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    class BrokenConfig:
        @property
        def experimental_backends_enabled(self) -> bool:
            raise AssertionError("unexpected config bug")

    monkeypatch.setattr("keyrgb.core.config.Config", BrokenConfig)

    with pytest.raises(AssertionError, match="unexpected config bug"):
        experimental_backends_enabled()


def test_iter_backends_skips_factory_failures() -> None:
    specs = [
        BackendSpec(
            name="broken",
            priority=100,
            factory=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
        BackendSpec(
            name="ok",
            priority=1,
            factory=lambda: DummyBackend("ok", 1, True, confidence=50),
        ),
    ]

    backends = iter_backends(specs=specs)

    assert [backend.name for backend in backends] == ["ok"]


def test_iter_backends_propagates_unexpected_factory_failures() -> None:
    specs = [
        BackendSpec(
            name="broken",
            priority=100,
            factory=lambda: (_ for _ in ()).throw(AssertionError("unexpected factory bug")),
        ),
    ]

    with pytest.raises(AssertionError, match="unexpected factory bug"):
        iter_backends(specs=specs)


def test_probe_backend_returns_unavailable_when_probe_raises() -> None:
    class ProbeFailsBackend(DummyBackend):
        def probe(self) -> ProbeResult:
            raise RuntimeError("probe boom")

    result = _probe_backend(ProbeFailsBackend("broken-probe", 1, True))

    assert result.available is False
    assert result.confidence == 0
    assert result.reason == "probe exception: probe boom"


def test_probe_backend_propagates_unexpected_probe_failures() -> None:
    class ProbeFailsBackend(DummyBackend):
        def probe(self) -> ProbeResult:
            raise AssertionError("unexpected probe bug")

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        _probe_backend(ProbeFailsBackend("broken-probe", 1, True))


def test_probe_backend_returns_unavailable_when_is_available_fallback_raises() -> None:
    class AvailabilityFailsBackend:
        name = "broken-availability"
        priority = 1
        probe = None

        def is_available(self) -> bool:
            raise RuntimeError("availability boom")

    result = _probe_backend(AvailabilityFailsBackend())

    assert result.available is False
    assert result.confidence == 0
    assert result.reason == "is_available exception: availability boom"


def test_probe_backend_propagates_unexpected_is_available_failures() -> None:
    class AvailabilityFailsBackend:
        name = "broken-availability"
        priority = 1
        probe = None

        def is_available(self) -> bool:
            raise AssertionError("unexpected availability bug")

    with pytest.raises(AssertionError, match="unexpected availability bug"):
        _probe_backend(AvailabilityFailsBackend())
