from __future__ import annotations

import math

from src.tray.pollers import idle_power_polling as ipp


def test_read_logind_idle_seconds_returns_none_when_run_fails(monkeypatch):
    monkeypatch.setattr(ipp, "_run", lambda *a, **k: None)
    assert ipp._read_logind_idle_seconds(session_id="1") is None


def test_read_logind_idle_seconds_not_idle_returns_zero(monkeypatch):
    out = "IdleHint=no\nIdleSinceHintMonotonic=123\n"
    monkeypatch.setattr(ipp, "_run", lambda *a, **k: out)
    assert ipp._read_logind_idle_seconds(session_id="1") == 0.0


def test_read_logind_idle_seconds_idle_computes_delta(monkeypatch):
    # now_us = 10.0s => 10,000,000 us; idle_since=7,000,000 => idle=3.0s
    out = "IdleHint=yes\nIdleSinceHintMonotonic=7000000\n"
    monkeypatch.setattr(ipp, "_run", lambda *a, **k: out)
    monkeypatch.setattr(ipp.time, "monotonic", lambda: 10.0)

    idle_s = ipp._read_logind_idle_seconds(session_id="1")
    assert idle_s is not None
    assert math.isclose(float(idle_s), 3.0, rel_tol=0.0, abs_tol=1e-9)


def test_read_logind_idle_seconds_idle_since_missing_returns_none(monkeypatch):
    out = "IdleHint=yes\n"
    monkeypatch.setattr(ipp, "_run", lambda *a, **k: out)
    monkeypatch.setattr(ipp.time, "monotonic", lambda: 10.0)
    assert ipp._read_logind_idle_seconds(session_id="1") is None


def test_read_logind_idle_seconds_unknown_idlehint_returns_none(monkeypatch):
    out = "IdleHint=maybe\nIdleSinceHintMonotonic=1\n"
    monkeypatch.setattr(ipp, "_run", lambda *a, **k: out)
    assert ipp._read_logind_idle_seconds(session_id="1") is None
