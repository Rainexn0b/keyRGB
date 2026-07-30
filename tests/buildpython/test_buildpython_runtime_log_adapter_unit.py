from __future__ import annotations

from pathlib import Path

from buildpython.core import runtime_log


def test_buildpython_runtime_capture_delegates_to_diagnostics_owner(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _fake_capture(**kwargs: object) -> int:
        calls.append(kwargs)
        return 17

    monkeypatch.setattr(runtime_log, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(runtime_log, "_capture_runtime_log", _fake_capture)

    assert runtime_log.capture_runtime_log(mode="full", launcher="source") == 17
    assert calls == [
        {
            "mode": "full",
            "launcher": "source",
            "output_directory": tmp_path,
            "source_root": tmp_path,
        }
    ]
