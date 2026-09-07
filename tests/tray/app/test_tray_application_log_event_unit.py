from types import SimpleNamespace

import pytest

import keyrgb.tray.app.application as app


def test_log_event_formats_fields_sorted_and_throttles(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    logged = []

    times = iter([10.0, 10.2, 11.5])
    monkeypatch.setattr(app.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    class _Unrepr:
        def __repr__(self):
            raise RuntimeError("no repr")

    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)
    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)  # throttled
    app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)  # allowed

    assert len(logged) == 2
    assert logged[0].startswith("EVENT config:apply")
    # Fields are sorted and unrepr is handled.
    assert "a=1" in logged[0]
    assert "b=<unrepr>" in logged[0]


def test_log_event_bails_out_if_source_action_not_stringable(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(
        app.logger,
        "info",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("logged")),
    )

    class BadStr:
        def __str__(self):
            raise RuntimeError("no")

    app.KeyRGBTray._log_event(tray, BadStr(), BadStr(), x=1)


def test_log_event_propagates_unexpected_source_action_string_errors(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(
        app.logger,
        "info",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("logged")),
    )

    class BadStr:
        def __str__(self):
            raise AssertionError("unexpected string bug")

    with pytest.raises(AssertionError, match="unexpected string bug"):
        app.KeyRGBTray._log_event(tray, BadStr(), "act", x=1)


def test_log_event_logs_even_if_throttle_state_errors(monkeypatch):
    logged = []

    class BadMap(dict):
        def get(self, *_a, **_k):
            raise RuntimeError("nope")

        def __setitem__(self, *_a, **_k):
            raise RuntimeError("nope")

    tray = SimpleNamespace(_event_last_at=BadMap())

    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    app.KeyRGBTray._log_event(tray, "src", "act", a=1)
    assert logged == ["EVENT src:act a=1"]


def test_log_event_propagates_unexpected_field_repr_errors(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda *_a, **_k: None)

    class _Unrepr:
        def __repr__(self):
            raise AssertionError("unexpected repr bug")

    with pytest.raises(AssertionError, match="unexpected repr bug"):
        app.KeyRGBTray._log_event(tray, "config", "apply", b=_Unrepr(), a=1)


def test_log_event_propagates_unexpected_throttle_state_errors(monkeypatch):
    logged = []

    class BadMap(dict):
        def get(self, *_a, **_k):
            raise AssertionError("unexpected throttle bug")

    tray = SimpleNamespace(_event_last_at=BadMap())

    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda fmt, msg: logged.append(msg))

    with pytest.raises(AssertionError, match="unexpected throttle bug"):
        app.KeyRGBTray._log_event(tray, "src", "act", a=1)


def test_log_event_propagates_unexpected_logger_failures(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(
        app.logger, "info", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("unexpected logger bug"))
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        app.KeyRGBTray._log_event(tray, "src", "act", a=1)


def test_log_event_swallows_logger_failures(monkeypatch):
    tray = SimpleNamespace(_event_last_at={})
    monkeypatch.setattr(app.time, "monotonic", lambda: 123.0)
    monkeypatch.setattr(app.logger, "info", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no")))

    # Should not raise.
    app.KeyRGBTray._log_event(tray, "src", "act", a=1)


def test_log_exception_delegates_to_logger_exception(monkeypatch):
    calls = []

    def _exc(msg, exc):
        calls.append((msg, exc))

    monkeypatch.setattr(app.logger, "exception", _exc)
    tray = SimpleNamespace()
    err = RuntimeError("boom")

    app.KeyRGBTray._log_exception(tray, "hello", err)
    assert calls == [("hello", err)]
