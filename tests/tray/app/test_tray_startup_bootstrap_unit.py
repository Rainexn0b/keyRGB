import logging

import pytest

import src.tray.startup.bootstrap as bootstrap


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("KEYRGB_DEBUG", raising=False)


def test_configure_logging_noops_when_handlers_exist(monkeypatch):
    root_logger = logging.getLogger()
    dummy = logging.NullHandler()
    root_logger.addHandler(dummy)

    called = {"basic": 0}
    monkeypatch.setattr(
        bootstrap.logging,
        "basicConfig",
        lambda **_k: called.__setitem__("basic", called["basic"] + 1),
    )

    try:
        bootstrap.configure_logging()
        assert called["basic"] == 0
    finally:
        root_logger.removeHandler(dummy)


def test_configure_logging_sets_debug_level_when_env_set(monkeypatch):
    monkeypatch.setenv("KEYRGB_DEBUG", "1")

    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    root_logger.handlers = []

    captured = {}

    def _basicConfig(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(bootstrap.logging, "basicConfig", _basicConfig)

    try:
        bootstrap.configure_logging()

        assert captured["level"] == bootstrap.logging.DEBUG
        assert "%(levelname)s" in captured["format"]
    finally:
        root_logger.handlers = saved_handlers


def test_configure_logging_sets_info_level_when_env_missing(monkeypatch):
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    root_logger.handlers = []

    captured = {}

    def _basicConfig(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(bootstrap.logging, "basicConfig", _basicConfig)

    try:
        bootstrap.configure_logging()
        assert captured["level"] == bootstrap.logging.INFO
    finally:
        root_logger.handlers = saved_handlers


def test_log_startup_diagnostics_noops_without_debug(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "collect_diagnostics",
        lambda **_k: (_ for _ in ()).throw(AssertionError("called")),
    )
    bootstrap.log_startup_diagnostics_if_debug()


def test_log_startup_diagnostics_logs_when_debug(monkeypatch):
    monkeypatch.setenv("KEYRGB_DEBUG", "1")

    called = {"collect": 0, "format": 0, "debug": []}

    def _collect_diagnostics(*, include_usb: bool):
        called["collect"] += 1
        assert include_usb is True
        return {"ok": True}

    def _format(diag):
        called["format"] += 1
        assert diag == {"ok": True}
        return "DIAG"

    monkeypatch.setattr(bootstrap, "collect_diagnostics", _collect_diagnostics)
    monkeypatch.setattr(bootstrap, "format_diagnostics_text", _format)
    monkeypatch.setattr(bootstrap.logger, "debug", lambda fmt, msg: called["debug"].append((fmt, msg)))

    bootstrap.log_startup_diagnostics_if_debug()

    assert called["collect"] == 1
    assert called["format"] == 1
    assert called["debug"]
    assert "Startup diagnostics" in called["debug"][0][0]
    assert called["debug"][0][1] == "DIAG"


def test_log_startup_diagnostics_swallow_exceptions(monkeypatch):
    monkeypatch.setenv("KEYRGB_DEBUG", "1")

    monkeypatch.setattr(
        bootstrap,
        "collect_diagnostics",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("no")),
    )
    # Should not raise
    bootstrap.log_startup_diagnostics_if_debug()


def test_acquire_single_instance_or_exit_returns_when_lock_acquired(monkeypatch):
    monkeypatch.setattr(bootstrap.runtime, "acquire_single_instance_lock", lambda: True)
    monkeypatch.setattr(
        bootstrap.sys,
        "exit",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("exit")),
    )

    bootstrap.acquire_single_instance_or_exit()


def test_acquire_single_instance_or_exit_exits_0_when_lock_held(monkeypatch):
    monkeypatch.setattr(bootstrap.runtime, "acquire_single_instance_lock", lambda: False)

    calls = {"error": 0, "exit": []}
    monkeypatch.setattr(
        bootstrap.logger,
        "error",
        lambda *_a, **_k: calls.__setitem__("error", calls["error"] + 1),
    )
    monkeypatch.setattr(bootstrap.sys, "exit", lambda code: calls["exit"].append(code))

    bootstrap.acquire_single_instance_or_exit()

    assert calls["error"] == 1
    assert calls["exit"] == [0]
