from __future__ import annotations

import json
import re
from pathlib import Path

from ._architecture_validation_models import (
    _FLAG_MAP,
    ArchitectureAssignmentRule,
    ArchitectureAttributeRule,
    ArchitectureCallRule,
    ArchitectureForbiddenUnderLockCallRule,
    ArchitectureImportRule,
    ArchitectureKeywordExemption,
    ArchitectureLock,
    ArchitectureLockOrderRule,
    ArchitecturePattern,
    ArchitectureRule,
)


def load_architecture_rules(config_path: Path) -> list[ArchitectureRule]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_rules = payload.get("rules", [])

    rules: list[ArchitectureRule] = []
    for raw_rule in raw_rules:
        rule_id = str(raw_rule.get("id", "")).strip()
        description = str(raw_rule.get("description", "")).strip()
        severity = str(raw_rule.get("severity", "error")).strip().lower()
        corpus = raw_rule.get("corpus", {}) or {}
        include_globs = tuple(str(item) for item in (corpus.get("include", []) or []))
        exclude_globs = tuple(str(item) for item in (corpus.get("exclude", []) or []))

        if not rule_id:
            raise ValueError("architecture rule missing 'id'")
        if severity not in {"error", "warning"}:
            raise ValueError(f"architecture rule {rule_id!r} has invalid severity {severity!r}")
        if not include_globs:
            raise ValueError(f"architecture rule {rule_id!r} has no corpus include globs")

        patterns: list[ArchitecturePattern] = []
        for raw_pattern in raw_rule.get("patterns", []) or []:
            regex = str(raw_pattern.get("regex", "")).strip()
            message = str(raw_pattern.get("message", "")).strip()
            flags = str(raw_pattern.get("flags", "")).strip().lower()
            if not regex or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid pattern entry")
            patterns.append(
                ArchitecturePattern(
                    regex=regex,
                    message=message,
                    flags=flags,
                    compiled=re.compile(regex, _regex_flags(flags)),
                )
            )

        imports: list[ArchitectureImportRule] = []
        for raw_import in raw_rule.get("imports", []) or []:
            module = str(raw_import.get("module", "")).strip()
            message = str(raw_import.get("message", "")).strip()
            if not module or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid import entry")
            imports.append(ArchitectureImportRule(module=module, message=message))

        attributes: list[ArchitectureAttributeRule] = []
        for raw_attribute in raw_rule.get("attributes", []) or []:
            name = str(raw_attribute.get("name", "")).strip()
            message = str(raw_attribute.get("message", "")).strip()
            if not name or not message:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid attribute entry")
            attributes.append(ArchitectureAttributeRule(name=name, message=message))

        assignments: list[ArchitectureAssignmentRule] = []
        raw_assignments = raw_rule.get("assignments", raw_rule.get("assignment_rules", []))
        if raw_assignments is None:
            raw_assignments = []
        if not isinstance(raw_assignments, list):
            raise ValueError(f"architecture rule {rule_id!r} has invalid assignment rules")  # noqa: TRY004
        for raw_assignment in raw_assignments:
            if not isinstance(raw_assignment, dict):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")  # noqa: TRY004
            targets = _load_assignment_string_values(
                raw_assignment.get("targets", []), rule_id=rule_id, field="targets"
            )
            target_suffixes = _load_assignment_string_values(
                raw_assignment.get("target_suffixes", []), rule_id=rule_id, field="target_suffixes"
            )
            raw_message = raw_assignment.get("message", "")
            if not isinstance(raw_message, str) or not raw_message.strip():
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")
            message = raw_message.strip()
            if not targets and not target_suffixes:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid assignment entry")
            assignments.append(
                ArchitectureAssignmentRule(
                    targets=targets,
                    target_suffixes=target_suffixes,
                    message=message,
                )
            )

        calls: list[ArchitectureCallRule] = []
        raw_calls = raw_rule.get("calls", raw_rule.get("call_rules", [])) or []
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid call entry")  # noqa: TRY004
            receivers = tuple(str(item).strip() for item in (raw_call.get("receivers", []) or []) if str(item).strip())
            receiver_suffixes = tuple(
                str(item).strip() for item in (raw_call.get("receiver_suffixes", []) or []) if str(item).strip()
            )
            methods = tuple(str(item).strip() for item in (raw_call.get("methods", []) or []) if str(item).strip())
            allowed_files = tuple(
                str(item).strip() for item in (raw_call.get("allowed_files", []) or []) if str(item).strip()
            )
            required_locks = tuple(
                str(item).strip() for item in (raw_call.get("required_locks", []) or []) if str(item).strip()
            )
            skip_if_keywords: list[ArchitectureKeywordExemption] = []
            raw_exemptions = raw_call.get("skip_if_keywords", []) or []
            if not isinstance(raw_exemptions, list):
                raise ValueError(f"architecture rule {rule_id!r} has invalid keyword exemptions")  # noqa: TRY004
            for raw_exemption in raw_exemptions:
                if not isinstance(raw_exemption, dict):
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid keyword exemption")  # noqa: TRY004
                name = str(raw_exemption.get("name", "")).strip()
                if not name or "equals" not in raw_exemption:
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid keyword exemption")
                equals = raw_exemption["equals"]
                if equals is not None and not isinstance(equals, (bool, int, float, str)):
                    raise ValueError(f"architecture rule {rule_id!r} has a non-literal keyword exemption")
                skip_if_keywords.append(ArchitectureKeywordExemption(name=name, equals=equals))
            message = str(raw_call.get("message", "")).strip()
            lock_message = str(raw_call.get("lock_message", "")).strip()
            forbid_all = raw_call.get("forbid_all", False)
            if (
                (not receivers and not receiver_suffixes)
                or not methods
                or (not allowed_files and forbid_all is not True)
                or not message
                or (required_locks and not lock_message)
                or type(forbid_all) is not bool
            ):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid call entry")
            calls.append(
                ArchitectureCallRule(
                    receivers=receivers,
                    receiver_suffixes=receiver_suffixes,
                    methods=methods,
                    allowed_files=allowed_files,
                    required_locks=required_locks,
                    skip_if_keywords=tuple(skip_if_keywords),
                    message=message,
                    lock_message=lock_message,
                    forbid_all=forbid_all,
                )
            )

        forbidden_under_locks: list[ArchitectureForbiddenUnderLockCallRule] = []
        raw_forbidden = (
            raw_rule.get(
                "forbidden_under_locks",
                raw_rule.get(
                    "forbidden_calls_under_locks",
                    raw_rule.get("forbidden_calls_under_lock", raw_rule.get("forbidden_calls", [])),
                ),
            )
            or []
        )
        if not isinstance(raw_forbidden, list):
            raise ValueError(  # noqa: TRY004
                f"architecture rule {rule_id!r} has invalid forbidden-under-lock call rules"
            )
        for raw_forbidden_call in raw_forbidden:
            if not isinstance(raw_forbidden_call, dict):
                raise ValueError(  # noqa: TRY004
                    f"architecture rule {rule_id!r} has an invalid forbidden-under-lock call entry"
                )
            receivers = _load_string_values(raw_forbidden_call.get("receivers", []), rule_id=rule_id, field="receivers")
            receiver_suffixes = _load_string_values(
                raw_forbidden_call.get("receiver_suffixes", []), rule_id=rule_id, field="receiver_suffixes"
            )
            methods = _load_string_values(raw_forbidden_call.get("methods", []), rule_id=rule_id, field="methods")
            required_locks = _load_string_values(
                raw_forbidden_call.get("required_locks", raw_forbidden_call.get("locks", [])),
                rule_id=rule_id,
                field="required_locks",
            )
            match_any_receiver = raw_forbidden_call.get("match_any_receiver", False)
            message = str(raw_forbidden_call.get("message", "")).strip()
            if (
                (not receivers and not receiver_suffixes and match_any_receiver is not True)
                or not methods
                or not required_locks
                or not message
                or type(match_any_receiver) is not bool
            ):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid forbidden-under-lock call entry")
            forbidden_under_locks.append(
                ArchitectureForbiddenUnderLockCallRule(
                    receivers=receivers,
                    receiver_suffixes=receiver_suffixes,
                    methods=methods,
                    match_any_receiver=match_any_receiver,
                    required_locks=required_locks,
                    message=message,
                )
            )

        lock_orders = _load_lock_order_rules(raw_rule=raw_rule, rule_id=rule_id)
        if (
            not patterns
            and not imports
            and not attributes
            and not assignments
            and not calls
            and not forbidden_under_locks
            and not lock_orders
        ):
            raise ValueError(
                f"architecture rule {rule_id!r} has no patterns, import rules, attribute rules, call rules, "
                "assignment rules, forbidden-under-lock call rules, or lock-order rules"
            )

        rules.append(
            ArchitectureRule(
                rule_id=rule_id,
                description=description,
                severity=severity,
                include_globs=include_globs,
                exclude_globs=exclude_globs,
                patterns=tuple(patterns),
                imports=tuple(imports),
                attributes=tuple(attributes),
                assignments=tuple(assignments),
                calls=tuple(calls),
                forbidden_under_locks=tuple(forbidden_under_locks),
                lock_orders=tuple(lock_orders),
            )
        )

    return rules


def _regex_flags(raw_flags: str) -> int:
    flags = 0
    for flag in raw_flags:
        flags |= _FLAG_MAP.get(flag, 0)
    return flags


def _load_string_values(raw_values: object, *, rule_id: str, field: str) -> tuple[str, ...]:
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list) or any(not isinstance(value, str) or not value.strip() for value in raw_values):
        raise ValueError(f"architecture rule {rule_id!r} has invalid forbidden-under-lock {field}")
    return tuple(value.strip() for value in raw_values)


def _load_assignment_string_values(raw_values: object, *, rule_id: str, field: str) -> tuple[str, ...]:
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list) or any(not isinstance(value, str) or not value.strip() for value in raw_values):
        raise ValueError(f"architecture rule {rule_id!r} has invalid assignment {field}")
    return tuple(value.strip() for value in raw_values)


def _load_lock_order_rules(*, raw_rule: object, rule_id: str) -> list[ArchitectureLockOrderRule]:
    if not isinstance(raw_rule, dict):
        raise ValueError(f"architecture rule {rule_id!r} must be an object")  # noqa: TRY004
    raw_lock_orders = raw_rule.get(
        "lock_orders",
        raw_rule.get("lock_order", raw_rule.get("lock_order_rules", [])),
    )
    if raw_lock_orders is None:
        return []
    if isinstance(raw_lock_orders, dict):
        raw_lock_orders = [raw_lock_orders]
    if not isinstance(raw_lock_orders, list):
        raise ValueError(f"architecture rule {rule_id!r} has invalid lock-order rules")  # noqa: TRY004

    lock_orders: list[ArchitectureLockOrderRule] = []
    for raw_lock_order in raw_lock_orders:
        if not isinstance(raw_lock_order, dict):
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock-order entry")  # noqa: TRY004
        raw_locks = raw_lock_order.get("locks", raw_lock_order.get("levels", raw_lock_order.get("order")))
        raw_alias_map = raw_lock_order.get("aliases", {})
        message = str(raw_lock_order.get("message", "")).strip()
        if not isinstance(raw_locks, list) or len(raw_locks) < 2 or not message:
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock-order entry")
        if not isinstance(raw_alias_map, (dict, list)):
            raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias map")  # noqa: TRY004

        locks: list[ArchitectureLock] = []
        seen_names: set[str] = set()
        for raw_lock in raw_locks:
            if isinstance(raw_lock, str):
                name = raw_lock.strip()
                mapped_aliases = raw_alias_map.get(name, []) if isinstance(raw_alias_map, dict) else []
                if not isinstance(mapped_aliases, list):
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias list")  # noqa: TRY004
                aliases = tuple(str(alias).strip() for alias in mapped_aliases)
            elif isinstance(raw_lock, dict):
                name = str(raw_lock.get("name", "")).strip()
                raw_aliases = raw_lock.get("aliases", [])
                if not isinstance(raw_aliases, list):
                    raise ValueError(f"architecture rule {rule_id!r} has an invalid lock alias list")  # noqa: TRY004
                aliases = tuple(str(alias).strip() for alias in raw_aliases)
            else:
                raise ValueError(f"architecture rule {rule_id!r} has an invalid lock entry")  # noqa: TRY004
            if not name or any(not alias for alias in aliases):
                raise ValueError(f"architecture rule {rule_id!r} has an invalid lock entry")
            names = (name, *aliases)
            if len(set(names)) != len(names) or seen_names.intersection(names):
                raise ValueError(f"architecture rule {rule_id!r} has duplicate lock names or aliases")
            seen_names.update(names)
            locks.append(ArchitectureLock(name=name, aliases=aliases))
        lock_orders.append(ArchitectureLockOrderRule(locks=tuple(locks), message=message))
    return lock_orders
