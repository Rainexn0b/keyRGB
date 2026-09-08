from __future__ import annotations

import json
from pathlib import Path

import pytest

from buildpython.steps import step_architecture_validation
from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture


def _payload() -> dict:
    return {
        "rules": [
            {
                "id": "boundary",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "imports": [{"module": "forbidden", "message": "bad dependency"}],
            }
        ]
    }


@pytest.mark.parametrize("payload", [{}, [], {"rules": []}, {"rules": {}}, {"rules": [None]}])
def test_architecture_config_rejects_empty_or_malformed_rules(tmp_path, payload) -> None:
    config = tmp_path / "rules.json"
    config.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_architecture_rules(config)


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "corpus_string", "call_lock_typo"])
def test_architecture_config_rejects_silent_policy_weakening(tmp_path, mutation) -> None:
    payload = _payload()
    rule = payload["rules"][0]
    if mutation == "duplicate":
        payload["rules"].append(rule.copy())
    elif mutation == "unknown":
        rule["callz"] = []
    elif mutation == "corpus_string":
        rule["corpus"]["include"] = "keyrgb/**/*.py"
    else:
        rule["calls"] = [
            {
                "receivers": ["kb"],
                "methods": ["set_color"],
                "forbid_all": True,
                "message": "bad write",
                "require_locks": ["kb_lock"],
            }
        ]
    config = tmp_path / "rules.json"
    config.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_architecture_rules(config)


@pytest.mark.parametrize("failure", ["syntax", "encoding", "read", "empty_corpus"])
def test_architecture_runner_fails_when_scan_is_incomplete(tmp_path, monkeypatch, failure) -> None:
    config = tmp_path / "buildpython/config/architecture_rules.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(_payload()))
    source = tmp_path / "keyrgb/example.py"
    source.parent.mkdir()
    if failure != "empty_corpus":
        source.write_bytes(
            b"def broken(:\n" if failure == "syntax" else b"\xff" if failure == "encoding" else b"pass\n"
        )
    read_text = Path.read_text
    if failure == "read":

        def fail_source_read(path, *args, **kwargs):
            if path == source:
                raise PermissionError("unreadable fixture")
            return read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fail_source_read)
    monkeypatch.setattr(step_architecture_validation, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_architecture_validation, "buildlog_dir", lambda: tmp_path / "reports")
    result = step_architecture_validation.architecture_validation_runner()
    assert result.exit_code == 1
    assert "matches no files" in result.stderr if failure == "empty_corpus" else "keyrgb/example.py" in result.stderr


def test_scanner_reads_each_source_once_for_multiple_rules(tmp_path, monkeypatch) -> None:
    payload = _payload()
    payload["rules"].append({**payload["rules"][0], "id": "second"})
    config = tmp_path / "rules.json"
    config.write_text(json.dumps(payload))
    rules = load_architecture_rules(config)
    source = tmp_path / "keyrgb/example.py"
    source.parent.mkdir()
    source.write_text("import forbidden\n")
    reads = []
    original = Path.read_text

    def read(path, *args, **kwargs):
        reads.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    result = scan_architecture(tmp_path, rules)
    assert reads == [source]
    assert len(result.findings) == 2
