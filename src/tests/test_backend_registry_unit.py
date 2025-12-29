from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.core.backends.base import ProbeResult
from src.core.backends.registry import BackendSpec, select_backend


@dataclass
class DummyBackend:
    name: str
    priority: int
    available: bool
    confidence: int = 50

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


def test_select_backend_auto_picks_highest_priority_available(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="low", priority=10, factory=lambda: DummyBackend("low", 10, True, confidence=50)),
        BackendSpec(name="high", priority=50, factory=lambda: DummyBackend("high", 50, True, confidence=50)),
        BackendSpec(name="missing", priority=999, factory=lambda: DummyBackend("missing", 999, False, confidence=0)),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)

    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "high"


def test_select_backend_auto_prefers_higher_confidence_over_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="prio", priority=100, factory=lambda: DummyBackend("prio", 100, True, confidence=10)),
        BackendSpec(name="conf", priority=1, factory=lambda: DummyBackend("conf", 1, True, confidence=90)),
    ]

    monkeypatch.delenv("KEYRGB_BACKEND", raising=False)
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "conf"


def test_select_backend_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="a", priority=1, factory=lambda: DummyBackend("a", 1, True, confidence=50)),
        BackendSpec(name="b", priority=2, factory=lambda: DummyBackend("b", 2, True, confidence=50)),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    backend = select_backend(specs=specs)
    assert backend is not None
    assert backend.name == "a"


def test_select_backend_requested_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="a", priority=1, factory=lambda: DummyBackend("a", 1, True, confidence=50)),
        BackendSpec(name="b", priority=2, factory=lambda: DummyBackend("b", 2, True, confidence=50)),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    backend = select_backend(requested="b", specs=specs)
    assert backend is not None
    assert backend.name == "b"


def test_select_backend_returns_none_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="a", priority=1, factory=lambda: DummyBackend("a", 1, False, confidence=0)),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "a")
    assert select_backend(specs=specs) is None


def test_select_backend_returns_none_when_unknown_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    specs = [
        BackendSpec(name="a", priority=1, factory=lambda: DummyBackend("a", 1, True, confidence=50)),
    ]

    monkeypatch.setenv("KEYRGB_BACKEND", "does-not-exist")
    assert select_backend(specs=specs) is None
