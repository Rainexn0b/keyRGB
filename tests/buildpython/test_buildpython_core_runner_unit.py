from __future__ import annotations

from types import SimpleNamespace

import pytest

import buildpython.core.runner as runner


def test_is_module_available_checks_module_spec(monkeypatch) -> None:
    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda name: SimpleNamespace() if name == "ruff" else None,
    )

    assert runner._is_module_available("ruff") is True
    assert runner._is_module_available("missing-module") is False


def test_is_module_available_propagates_unexpected_find_spec_failures(monkeypatch) -> None:
    def fake_find_spec(_name: str):
        raise AssertionError("unexpected spec failure")

    monkeypatch.setattr(runner.importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(AssertionError, match="unexpected spec failure"):
        runner._is_module_available("ruff")