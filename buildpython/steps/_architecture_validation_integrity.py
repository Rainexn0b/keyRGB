"""Reject configurations that accidentally disable architecture enforcement."""

from __future__ import annotations

from pathlib import Path

from ._architecture_validation_helpers import _iter_rule_files
from ._architecture_validation_models import ArchitectureRule

_RULE_FIELDS = {
    "id",
    "description",
    "severity",
    "corpus",
    "patterns",
    "imports",
    "attributes",
    "assignments",
    "assignment_rules",
    "calls",
    "call_rules",
    "forbidden_under_locks",
    "forbidden_calls_under_locks",
    "forbidden_calls_under_lock",
    "forbidden_calls",
    "lock_orders",
    "lock_order",
    "lock_order_rules",
}
_CALL_FIELDS = {
    "receivers",
    "receiver_suffixes",
    "methods",
    "allowed_files",
    "required_locks",
    "skip_if_keywords",
    "message",
    "lock_message",
    "forbid_all",
}


def validate_rule_payload(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {"rules"}:
        raise ValueError("Architecture config must be an object containing only 'rules'")
    rules = payload["rules"]
    if not isinstance(rules, list) or not rules:
        raise ValueError("Architecture config must contain a non-empty rules list")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Architecture rule must be an object")  # noqa: TRY004
        _check_fields(rule, _RULE_FIELDS, "architecture rule")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError("architecture rule missing 'id'")
        if rule_id.strip() in seen:
            raise ValueError(f"Duplicate architecture rule id: {rule_id!r}")
        seen.add(rule_id.strip())
        corpus = rule.get("corpus")
        if not isinstance(corpus, dict):
            raise ValueError(f"architecture rule {rule_id!r} must have a corpus object")  # noqa: TRY004
        _check_fields(corpus, {"include", "exclude"}, f"{rule_id} corpus")
        for field in ("include", "exclude"):
            _check_strings(corpus.get(field, []), f"{rule_id} corpus {field}")
        for field in ("patterns", "imports", "attributes", "calls", "call_rules"):
            entries = rule.get(field, [])
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                raise ValueError(f"architecture rule {rule_id!r} has invalid {field} entries")
            if field not in {"calls", "call_rules"}:
                continue
            for call in entries:
                _check_fields(call, _CALL_FIELDS, f"{rule_id} call")
                for name in ("receivers", "receiver_suffixes", "methods", "allowed_files", "required_locks"):
                    _check_strings(call.get(name, []), f"{rule_id} call {name}")


def _check_fields(value: dict, allowed: set[str], context: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown fields in {context}: {', '.join(sorted(unknown))}")


def _check_strings(value: object, context: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{context} must be a list of non-empty strings")


def validate_rule_corpora(root: Path, rules: list[ArchitectureRule]) -> None:
    """The production gate must not pass after a rename empties a rule's corpus.

    Kept separate from scan_architecture so focused fixture scans can select a
    subset of the repo (including a deliberately excluded owner).
    """

    for rule in rules:
        if not _iter_rule_files(root=root, rule=rule):
            raise ValueError(f"Architecture rule {rule.rule_id!r} matches no files after exclusions")
