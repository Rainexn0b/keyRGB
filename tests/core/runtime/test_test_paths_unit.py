from __future__ import annotations

import sys

import tests._paths as test_paths


def test_ensure_repo_root_on_sys_path_uses_runtime_helper_when_available(monkeypatch) -> None:
    calls: list[str] = []

    def _ensure(anchor: str) -> str:
        calls.append(anchor)
        return "/resolved/root"

    monkeypatch.setattr(test_paths, "_runtime_path_helpers", lambda: (_ensure, None))

    assert test_paths.ensure_repo_root_on_sys_path() == "/resolved/root"
    assert calls == [test_paths.__file__]


def test_ensure_repo_root_on_sys_path_falls_back_to_inserting_repo_root_once(monkeypatch) -> None:
    original_path = list(sys.path)
    try:
        monkeypatch.setattr(test_paths, "_runtime_path_helpers", lambda: (None, None))
        monkeypatch.setattr(test_paths, "REPO_ROOT", "/tmp/keyrgb-test-root")
        sys.path[:] = [entry for entry in original_path if entry != "/tmp/keyrgb-test-root"]

        assert test_paths.ensure_repo_root_on_sys_path() == "/tmp/keyrgb-test-root"
        assert sys.path[0] == "/tmp/keyrgb-test-root"

        assert test_paths.ensure_repo_root_on_sys_path() == "/tmp/keyrgb-test-root"
        assert sys.path.count("/tmp/keyrgb-test-root") == 1
    finally:
        sys.path[:] = original_path