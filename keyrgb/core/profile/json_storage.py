from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCK_FILENAME = ".profile-json.lock"


def _lock_path_for(path: Path) -> Path:
    """Use one config-level lock for profile trees and their marker files."""

    for parent in path.parents:
        if parent.name == "profiles":
            return parent.parent / _LOCK_FILENAME
    return path.parent / _LOCK_FILENAME


@contextmanager
def _profile_json_lock(path: Path, *, exclusive: bool) -> Iterator[None]:
    """Lock profile JSON operations that share one configuration root."""

    lock_path = _lock_path_for(path)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_json_unlocked(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_json_strict(path: Path) -> object:
    """Read one JSON value under the directory's shared profile lock."""

    with _profile_json_lock(path, exclusive=False):
        return _read_json_unlocked(path)


def read_json(path: Path) -> object | None:
    try:
        return read_json_strict(path)
    except (OSError, json.JSONDecodeError):
        return None


def _replace_with_serialized_json(path: Path, serialized: str) -> None:
    """Write, flush, and atomically replace one JSON target while locked."""

    tmp_fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    fd_open = True
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
            fd_open = False
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if fd_open:
            os.close(tmp_fd)
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def write_json_atomic(path: Path, payload: object, *, indent: int = 2, sort_keys: bool = True) -> None:
    serialized = json.dumps(payload, indent=indent, sort_keys=sort_keys)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _profile_json_lock(path, exclusive=True):
        _replace_with_serialized_json(path, serialized)


def update_json_atomic(
    path: Path,
    update: Callable[[object | None], object],
    *,
    indent: int = 2,
    sort_keys: bool = True,
) -> object:
    """Apply one read-modify-write transaction under an exclusive lock."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with _profile_json_lock(path, exclusive=True):
        try:
            current = _read_json_unlocked(path)
        except (FileNotFoundError, json.JSONDecodeError):
            current = None
        payload = update(current)
        serialized = json.dumps(payload, indent=indent, sort_keys=sort_keys)
        _replace_with_serialized_json(path, serialized)
    return payload
