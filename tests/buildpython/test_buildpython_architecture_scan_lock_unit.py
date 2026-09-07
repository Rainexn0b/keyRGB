from __future__ import annotations

import pytest

from tests.buildpython._architecture_validation_unit_support import (
    _scan_forbidden_under_lock,
    _scan_lock_order,
)


def test_scan_lock_order_accepts_full_order_and_aliases(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """with self._start_lock:
    with engine.kb_lock:
        with tray.engine._brightness_fade_lock:
            pass
""",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "inner_lock", "outer_locks"),
    [
        ("with engine.kb_lock:\n    with self._start_lock:\n        pass\n", "_start_lock", ("engine.kb_lock",)),
        (
            "with tray.engine._brightness_fade_lock:\n    with kb_lock:\n        pass\n",
            "kb_lock",
            ("tray.engine._brightness_fade_lock",),
        ),
        (
            "with _brightness_fade_lock:\n    with self._start_lock:\n        pass\n",
            "_start_lock",
            ("_brightness_fade_lock",),
        ),
    ],
)
def test_scan_lock_order_reports_each_inversion(
    tmp_path, source: str, inner_lock: str, outer_locks: tuple[str, ...]
) -> None:
    result = _scan_lock_order(tmp_path, source)

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.line == 2
    assert finding.lock == inner_lock
    assert finding.outer_locks == outer_locks
    assert finding.regex.startswith("lock-order:")


def test_scan_lock_order_allows_same_level_reentrant_acquisition(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with kb_lock:\n    with self.kb_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_ignores_unrelated_locks(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with unrelated_lock:\n    with self._start_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_does_not_match_unconfigured_terminal_lock_names(tmp_path) -> None:
    result = _scan_lock_order(tmp_path, "with other.kb_lock:\n    with self._start_lock:\n        pass\n")

    assert result.findings == ()


def test_scan_lock_order_supports_async_with(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """async def apply():
    async with self._start_lock:
        async with engine.kb_lock:
            async with tray.engine._brightness_fade_lock:
                pass
""",
    )

    assert result.findings == ()


def test_scan_lock_order_nested_function_does_not_inherit_outer_lock(tmp_path) -> None:
    result = _scan_lock_order(
        tmp_path,
        """with self._brightness_fade_lock:
    def later():
        with self._start_lock:
            pass
""",
    )

    assert result.findings == ()


@pytest.mark.parametrize(
    ("source", "method"),
    [
        ("with kb_lock:\n    time.sleep(1)\n", "time.sleep"),
        ("with self.kb_lock:\n    worker.join()\n", "worker.join"),
        ("with kb_lock:\n    process.wait()\n", "process.wait"),
        ("with kb_lock:\n    process.communicate()\n", "process.communicate"),
        ("with kb_lock:\n    subprocess.run([])\n", "subprocess.run"),
        ("with kb_lock:\n    subprocess.call([])\n", "subprocess.call"),
        ("with kb_lock:\n    subprocess.check_call([])\n", "subprocess.check_call"),
        ("with kb_lock:\n    subprocess.check_output([])\n", "subprocess.check_output"),
        ("with kb_lock:\n    subprocess.Popen([])\n", "subprocess.Popen"),
    ],
)
def test_forbidden_under_lock_reports_blocking_call(tmp_path, source: str, method: str) -> None:
    result = _scan_forbidden_under_lock(tmp_path, source)

    assert len(result.findings) == 1
    assert result.findings[0].regex == f"forbidden-under-lock:{method}"
    assert result.findings[0].lock in {"kb_lock", "self.kb_lock"}


@pytest.mark.parametrize("lock", ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"])
@pytest.mark.parametrize(
    ("imports", "call", "method"),
    [
        ("from time import sleep", "sleep(1)", "time.sleep"),
        ("from time import sleep as pause", "pause(1)", "time.sleep"),
        ("import time as clock", "clock.sleep(1)", "time.sleep"),
        ("from subprocess import run", "run([])", "subprocess.run"),
        ("from subprocess import run as launch", "launch([])", "subprocess.run"),
        ("import subprocess as commands", "commands.run([])", "subprocess.run"),
        ("from subprocess import Popen", "Popen([])", "subprocess.Popen"),
        ("from subprocess import Popen as launch", "launch([])", "subprocess.Popen"),
        ("import subprocess as commands", "commands.Popen([])", "subprocess.Popen"),
    ],
)
def test_forbidden_under_lock_canonicalizes_imported_and_module_aliases(
    tmp_path, lock: str, imports: str, call: str, method: str
) -> None:
    result = _scan_forbidden_under_lock(tmp_path, f"{imports}\nwith {lock}:\n    {call}\n")

    assert len(result.findings) == 1
    assert result.findings[0].regex == f"forbidden-under-lock:{method}"
    assert result.findings[0].lock == lock


def test_forbidden_under_lock_does_not_treat_shadowed_callback_as_subprocess_run(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        "from subprocess import run\ndef invoke(run):\n    with kb_lock:\n        run([])\n",
    )

    assert result.findings == ()


def test_forbidden_under_lock_supports_suffix_and_match_any_receivers(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """with kb_lock:
    service.process.run([])
    thread.join()
    event.wait()
    child.communicate()
""",
    )

    assert [finding.regex for finding in result.findings] == [
        "forbidden-under-lock:service.process.run",
        "forbidden-under-lock:thread.join",
        "forbidden-under-lock:event.wait",
        "forbidden-under-lock:child.communicate",
    ]


def test_forbidden_under_lock_allows_outside_lock_and_nonblocking_calls(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """time.sleep(1)
with kb_lock:
    keyboard.set_color((1, 2, 3))
    thread.start()
""",
    )

    assert result.findings == ()


def test_forbidden_under_lock_supports_async_with_and_nested_function_scope(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """async def apply():
    async with self.kb_lock:
        time.sleep(1)
        def later():
            time.sleep(1)
""",
    )

    assert len(result.findings) == 1
    assert result.findings[0].line == 3


def test_forbidden_under_lock_does_not_include_bare_methods_or_arbitrary_callbacks(tmp_path) -> None:
    result = _scan_forbidden_under_lock(
        tmp_path,
        """with kb_lock:
    sleep(1)
    callback()
""",
    )

    assert result.findings == ()
