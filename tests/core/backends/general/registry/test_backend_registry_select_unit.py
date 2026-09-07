from __future__ import annotations

from dataclasses import dataclass

import pytest

from keyrgb.core.backends.base import (
    BackendStability,
    ExperimentalEvidence,
    ProbeResult,
)
from keyrgb.core.backends.registry import (
    BackendSpec,
    build_backend_selection_report,
    select_backend,
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


def test_select_backend_auto_picks_highest_priority_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="low",
            priority=10,
            factory=lambda: DummyBackend("low", 10, True, confidence=50),
        ),
        BackendSpec(
            name="high",
            priority=50,
            factory=lambda: DummyBackend("high", 50, True, confidence=50),
        ),
        BackendSpec(
            name="missing",
            priority=999,
            factory=lambda: DummyBackend("missing", 999, False, confidence=0),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "high"


def test_select_backend_auto_prefers_higher_confidence_over_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="prio",
            priority=100,
            factory=lambda: DummyBackend("prio", 100, True, confidence=10),
        ),
        BackendSpec(
            name="conf",
            priority=1,
            factory=lambda: DummyBackend("conf", 1, True, confidence=90),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "conf"


def test_select_backend_auto_prefers_usable_sysfs_over_higher_confidence_usb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8291r3_perkey",
            priority=100,
            factory=lambda: DummyBackend("ite8291r3_perkey", 100, True, confidence=90),
        ),
        BackendSpec(
            name="sysfs-leds",
            priority=150,
            factory=lambda: DummyBackend("sysfs-leds", 150, True, confidence=70),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "sysfs-leds"


def test_selection_report_is_canonical_and_probes_each_backend_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_calls: list[str] = []

    class CountingBackend(DummyBackend):
        def probe(self) -> ProbeResult:
            probe_calls.append(self.name)
            return super().probe()

    backends = [
        CountingBackend("ite8291r3_perkey", 100, True, confidence=95),
        CountingBackend("sysfs-leds", 10, True, confidence=60),
    ]
    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)

    report = build_backend_selection_report(backends)

    assert report.selected is backends[1]
    assert [evaluation.backend.name for evaluation in report.candidates] == [
        "sysfs-leds",
        "ite8291r3_perkey",
    ]
    assert [evaluation.auto_safety_tier for evaluation in report.candidates] == [1, 0]
    assert probe_calls == ["ite8291r3_perkey", "sysfs-leds"]


def test_select_backend_auto_uses_usb_when_sysfs_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8291r3_perkey",
            priority=100,
            factory=lambda: DummyBackend("ite8291r3_perkey", 100, True, confidence=90),
        ),
        BackendSpec(
            name="sysfs-leds",
            priority=150,
            factory=lambda: DummyBackend("sysfs-leds", 150, False, confidence=0),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "ite8291r3_perkey"


def test_select_backend_requested_usb_bypasses_sysfs_auto_preference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8291r3_perkey",
            priority=100,
            factory=lambda: DummyBackend("ite8291r3_perkey", 100, True, confidence=90),
        ),
        BackendSpec(
            name="sysfs-leds",
            priority=150,
            factory=lambda: DummyBackend("sysfs-leds", 150, True, confidence=85),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "ite8291r3_perkey")

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "ite8291r3_perkey"


def test_select_backend_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(
            name="a",
            priority=1,
            factory=lambda: DummyBackend("a", 1, True, confidence=50),
        ),
        BackendSpec(
            name="b",
            priority=2,
            factory=lambda: DummyBackend("b", 2, True, confidence=50),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "a"


def test_select_backend_requested_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="a",
            priority=1,
            factory=lambda: DummyBackend("a", 1, True, confidence=50),
        ),
        BackendSpec(
            name="b",
            priority=2,
            factory=lambda: DummyBackend("b", 2, True, confidence=50),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    backend = select_backend(requested="b", specs=specs)
    assert backend is not None
    assert backend.name == "b"


def test_select_backend_returns_none_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="a",
            priority=1,
            factory=lambda: DummyBackend("a", 1, False, confidence=0),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    assert select_backend(specs=specs) is None


def test_select_backend_returns_none_when_unknown_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="a",
            priority=1,
            factory=lambda: DummyBackend("a", 1, True, confidence=50),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "does-not-exist")
    assert select_backend(specs=specs) is None


def test_select_backend_resolves_deprecated_alias_to_canonical_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8258_zones_lenovo_legion",
            priority=1,
            factory=lambda: DummyBackend("ite8258_zones_lenovo_legion", 1, True, confidence=50),
        ),
    ]

    # Old alias "ite8258" should resolve to canonical "ite8258_zones_lenovo_legion"
    monkeypatch.setenv("KEYRGB_BACKEND", "ite8258")
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "ite8258_zones_lenovo_legion"


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("ite8291r3", "ite8291r3_perkey"),
        ("ite8910", "ite8910_perkey"),
        ("ite8291", "ite8291_perkey"),
        ("ite8291-zones", "ite8291_zones_clevo"),
        ("ite8258-chassis", "ite8258_perkey_chassis"),
        ("ite8258_chassis", "ite8258_perkey_chassis"),
        ("ite8258_perkey_chassis_logo_neon_vent_lenovo_legion", "ite8258_perkey_chassis"),
        ("ite8295-zones", "ite8295_zones_lenovo_ideapad"),
        ("ite8233", "ite8233_none_chassis_lightbar_clevo"),
        ("ite8297", "ite8297_uniform"),
    ],
)
def test_select_backend_resolves_all_deprecated_aliases(
    monkeypatch: pytest.MonkeyPatch,
    alias: str,
    canonical: str,
) -> None:
    specs = [
        BackendSpec(
            name=canonical,
            priority=1,
            factory=lambda: DummyBackend(canonical, 1, True, confidence=50),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", alias)
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == canonical


def test_select_backend_skips_experimental_backend_when_opt_in_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8910_perkey",
            priority=100,
            factory=lambda: DummyBackend(
                "ite8910_perkey",
                100,
                True,
                confidence=90,
                stability=BackendStability.EXPERIMENTAL,
            ),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)
    monkeypatch.delenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", raising=False)

    assert select_backend(specs=specs) is None


def test_select_backend_allows_experimental_backend_when_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8910_perkey",
            priority=100,
            factory=lambda: DummyBackend(
                "ite8910_perkey",
                100,
                True,
                confidence=90,
                stability=BackendStability.EXPERIMENTAL,
            ),
        ),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "ite8910_perkey"


def test_select_backend_never_selects_dormant_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = [
        BackendSpec(
            name="ite8297_uniform",
            priority=100,
            factory=lambda: DummyBackend(
                "ite8297_uniform",
                100,
                True,
                confidence=90,
                stability=BackendStability.DORMANT,
            ),
        ),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "ite8297_uniform")
    monkeypatch.setenv("KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS", "1")

    assert select_backend(specs=specs) is None
