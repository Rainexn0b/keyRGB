from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def test_serialization_failure_preserves_existing_target(tmp_path: Path) -> None:
    from src.core.profile.json_storage import write_json_atomic

    target = tmp_path / "profile.json"
    original = {"profile": "last-valid"}
    target.write_text(json.dumps(original), encoding="utf-8")
    circular: list[object] = []
    circular.append(circular)

    with pytest.raises(ValueError, match="Circular reference"):
        write_json_atomic(target, circular)

    assert json.loads(target.read_text(encoding="utf-8")) == original
    assert not target.with_suffix(".json.tmp").exists()


def test_replace_failure_preserves_existing_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.profile.json_storage import write_json_atomic

    target = tmp_path / "profile.json"
    original = {"profile": "last-valid"}
    target.write_text(json.dumps(original), encoding="utf-8")

    def fail_replace(_source, _target) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_json_atomic(target, {"profile": "new"})

    assert json.loads(target.read_text(encoding="utf-8")) == original
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_successful_write_leaves_valid_json_and_no_temp_file(tmp_path: Path) -> None:
    from src.core.profile.json_storage import write_json_atomic

    target = tmp_path / "nested" / "profile.json"
    payload = {"profile": "new", "colors": [[1, 2, 3]]}

    write_json_atomic(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_suffix(".json.tmp").exists()


def test_successful_write_flushes_file_content_before_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.profile.json_storage import write_json_atomic

    fsync_calls: list[int] = []
    monkeypatch.setattr(os, "fsync", fsync_calls.append)

    write_json_atomic(tmp_path / "profile.json", {"profile": "durable"})

    assert fsync_calls


def test_concurrent_writers_complete_without_sharing_a_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.profile.json_storage import write_json_atomic

    target = tmp_path / "profile.json"
    fixed_temp = target.with_suffix(".json.tmp")
    writes_reached = threading.Barrier(2)
    original_write_text = Path.write_text

    def synchronized_write_text(self: Path, *args, **kwargs):
        result = original_write_text(self, *args, **kwargs)
        if self == fixed_temp:
            writes_reached.wait(timeout=2.0)
        return result

    monkeypatch.setattr(Path, "write_text", synchronized_write_text)
    payloads = ({"writer": 1}, {"writer": 2})

    def write(payload: dict[str, int]) -> None:
        write_json_atomic(target, payload)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write, payload) for payload in payloads]
        for future in futures:
            future.result(timeout=3.0)

    assert json.loads(target.read_text(encoding="utf-8")) in payloads
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_reader_waits_for_locked_update_and_observes_completed_payload(tmp_path: Path) -> None:
    from src.core.profile.json_storage import read_json, update_json_atomic, write_json_atomic

    target = tmp_path / "profile.json"
    write_json_atomic(target, {"value": "old"})
    update_started = threading.Event()
    release_update = threading.Event()
    reader_started = threading.Event()

    def update(_current: object | None) -> object:
        update_started.set()
        assert release_update.wait(timeout=2.0)
        return {"value": "new"}

    def read() -> object | None:
        reader_started.set()
        return read_json(target)

    with ThreadPoolExecutor(max_workers=2) as executor:
        update_future = executor.submit(update_json_atomic, target, update)
        assert update_started.wait(timeout=2.0)
        read_future = executor.submit(read)
        assert reader_started.wait(timeout=2.0)
        assert not read_future.done()
        release_update.set()

        assert update_future.result(timeout=3.0) == {"value": "new"}
        assert read_future.result(timeout=3.0) == {"value": "new"}
