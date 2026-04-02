from __future__ import annotations

import logging

from src.core.utils import logging_utils


def test_log_throttled_throttles_repeated_logs_for_same_logger_and_key(caplog, monkeypatch) -> None:
    logger = logging.getLogger("tests.logging_utils.same")
    logging_utils._last_log_times.clear()
    monkeypatch.setattr(logging_utils.time, "monotonic", lambda: 10.0)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        first = logging_utils.log_throttled(
            logger,
            "demo",
            interval_s=60,
            level=logging.WARNING,
            msg="first message",
        )
        second = logging_utils.log_throttled(
            logger,
            "demo",
            interval_s=60,
            level=logging.WARNING,
            msg="second message",
        )

    assert first is True
    assert second is False
    assert [record.getMessage() for record in caplog.records] == ["first message"]


def test_log_throttled_does_not_cross_throttle_different_loggers(caplog) -> None:
    logger_one = logging.getLogger("tests.logging_utils.one")
    logger_two = logging.getLogger("tests.logging_utils.two")
    logging_utils._last_log_times.clear()

    with caplog.at_level(logging.WARNING):
        first = logging_utils.log_throttled(
            logger_one,
            "shared-key",
            interval_s=60,
            level=logging.WARNING,
            msg="message one",
        )
        second = logging_utils.log_throttled(
            logger_two,
            "shared-key",
            interval_s=60,
            level=logging.WARNING,
            msg="message two",
        )

    assert first is True
    assert second is True
    assert [record.getMessage() for record in caplog.records] == ["message one", "message two"]