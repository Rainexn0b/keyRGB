from __future__ import annotations

import json

from buildpython.steps.architecture_validation import load_architecture_rules, scan_architecture


def _call_rule_payload(
    *,
    allowed_files: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> dict:
    return {
        "rules": [
            {
                "id": "primary-lighting-write-ownership",
                "description": "Primary lighting writes",
                "severity": "error",
                "corpus": {
                    "include": ["keyrgb/**/*.py"],
                    "exclude": exclude_globs or [],
                },
                "calls": [
                    {
                        "receivers": ["kb", "keyboard"],
                        "receiver_suffixes": [".kb", ".keyboard"],
                        "methods": [
                            "set_brightness",
                            "set_color",
                            "set_key_colors",
                            "enable_user_mode",
                            "turn_off",
                            "set_effect",
                        ],
                        "allowed_files": allowed_files or ["keyrgb/core/effects/fades.py"],
                        "required_locks": ["kb_lock", "engine.kb_lock", "self.kb_lock", "tray.engine.kb_lock"],
                        "message": "unapproved primary lighting owner",
                        "lock_message": "unlocked primary lighting write",
                    }
                ],
            }
        ]
    }


def _scan_call_rule(
    tmp_path,
    source: str,
    *,
    relative_path: str = "keyrgb/core/effects/fades.py",
    exclude_globs: list[str] | None = None,
):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(
        json.dumps(_call_rule_payload(exclude_globs=exclude_globs)),
        encoding="utf-8",
    )
    return scan_architecture(root, load_architecture_rules(config_path))


def _assignment_rule_payload() -> dict:
    return {
        "rules": [
            {
                "id": "no-state-assignments",
                "description": "Observation modules do not mutate state",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "assignments": [
                    {
                        "targets": ["desired.exact", "named_expr"],
                        "target_suffixes": [".forbidden", ".compat"],
                        "message": "direct state assignment",
                    }
                ],
            }
        ]
    }


def _scan_assignment_rule(tmp_path, source: str, *, relative_path: str = "keyrgb/runtime.py"):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_assignment_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _forbidden_under_lock_payload() -> dict:
    return {
        "rules": [
            {
                "id": "no-blocking-under-lock",
                "description": "Blocking calls do not belong under the keyboard lock",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "forbidden_under_locks": [
                    {
                        "receivers": ["time"],
                        "methods": ["sleep"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "sleep under keyboard lock",
                    },
                    {
                        "receiver_suffixes": [".process"],
                        "methods": ["run"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "process run under keyboard lock",
                    },
                    {
                        "methods": ["join", "wait", "communicate"],
                        "match_any_receiver": True,
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "blocking method under keyboard lock",
                    },
                    {
                        "receivers": ["subprocess"],
                        "methods": ["run", "call", "check_call", "check_output", "Popen"],
                        "required_locks": ["kb_lock", "self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                        "message": "subprocess under keyboard lock",
                    },
                ],
            }
        ]
    }


def _scan_forbidden_under_lock(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbidden_under_lock_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _lock_order_payload() -> dict:
    return {
        "rules": [
            {
                "id": "runtime-lock-order",
                "description": "Runtime lock order",
                "severity": "error",
                "corpus": {"include": ["keyrgb/**/*.py"]},
                "lock_orders": [
                    {
                        "locks": [
                            {
                                "name": "_start_lock",
                                "aliases": ["self._start_lock", "engine._start_lock", "tray.engine._start_lock"],
                            },
                            {
                                "name": "kb_lock",
                                "aliases": ["self.kb_lock", "engine.kb_lock", "tray.engine.kb_lock"],
                            },
                            {
                                "name": "_brightness_fade_lock",
                                "aliases": [
                                    "self._brightness_fade_lock",
                                    "engine._brightness_fade_lock",
                                    "tray.engine._brightness_fade_lock",
                                ],
                            },
                        ],
                        "message": "Runtime locks are out of order",
                    }
                ],
            }
        ]
    }


def _scan_lock_order(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_lock_order_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _poller_engine_call_rule_payload() -> dict:
    return {
        "rules": [
            {
                "id": "pollers-no-primary-engine-mutations",
                "description": "Pollers observe; approved leaves commit",
                "severity": "error",
                "corpus": {"include": ["keyrgb/tray/pollers/**/*.py"]},
                "calls": [
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["turn_off", "start_effect"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                        ],
                        "message": "poller primary engine mutation",
                    },
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["set_brightness"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                        ],
                        "skip_if_keywords": [{"name": "apply_to_hardware", "equals": False}],
                        "message": "poller primary brightness mutation",
                    },
                    {
                        "receivers": ["engine"],
                        "receiver_suffixes": [".engine"],
                        "methods": ["stop"],
                        "allowed_files": [
                            "keyrgb/tray/pollers/config_polling_internal/_apply_callbacks.py",
                            "keyrgb/tray/pollers/idle_power/_action_execution.py",
                            "keyrgb/tray/pollers/hardware/_controller_sleep.py",
                        ],
                        "message": "poller primary engine stop",
                    },
                ],
            }
        ]
    }


def _scan_poller_engine_call(
    tmp_path,
    source: str,
    *,
    relative_path: str = "keyrgb/tray/pollers/hardware_polling.py",
):
    root = tmp_path / "repo"
    target = root / relative_path
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_poller_engine_call_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))


def _forbid_all_call_rule_payload(*, forbid_all: object = True, allowed_files: list[str] | None = None) -> dict:
    payload = _call_rule_payload(allowed_files=["keyrgb/core/effects/fades.py"])
    call = payload["rules"][0]["calls"][0]
    call["allowed_files"] = [] if allowed_files is None else allowed_files
    call["forbid_all"] = forbid_all
    return payload


def _scan_forbid_all_call_rule(tmp_path, source: str):
    root = tmp_path / "repo"
    target = root / "keyrgb/runtime.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")
    config_path = tmp_path / "architecture_rules.json"
    config_path.write_text(json.dumps(_forbid_all_call_rule_payload()), encoding="utf-8")
    return scan_architecture(root, load_architecture_rules(config_path))
