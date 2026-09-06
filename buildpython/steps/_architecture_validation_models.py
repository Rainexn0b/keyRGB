from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitecturePattern:
    regex: str
    message: str
    flags: str
    compiled: re.Pattern[str]


@dataclass(frozen=True)
class ArchitectureImportRule:
    module: str
    message: str


@dataclass(frozen=True)
class ArchitectureAttributeRule:
    name: str
    message: str


@dataclass(frozen=True)
class ArchitectureAssignmentRule:
    targets: tuple[str, ...]
    target_suffixes: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ArchitectureKeywordExemption:
    name: str
    equals: object


@dataclass(frozen=True)
class ArchitectureCallRule:
    receivers: tuple[str, ...]
    receiver_suffixes: tuple[str, ...]
    methods: tuple[str, ...]
    allowed_files: tuple[str, ...]
    required_locks: tuple[str, ...]
    skip_if_keywords: tuple[ArchitectureKeywordExemption, ...]
    message: str
    lock_message: str
    forbid_all: bool = False


@dataclass(frozen=True)
class ArchitectureForbiddenUnderLockCallRule:
    receivers: tuple[str, ...]
    receiver_suffixes: tuple[str, ...]
    methods: tuple[str, ...]
    match_any_receiver: bool
    required_locks: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class ArchitectureLock:
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureLockOrderRule:
    locks: tuple[ArchitectureLock, ...]
    message: str


@dataclass(frozen=True)
class ArchitectureRule:
    rule_id: str
    description: str
    severity: str
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    patterns: tuple[ArchitecturePattern, ...]
    imports: tuple[ArchitectureImportRule, ...]
    attributes: tuple[ArchitectureAttributeRule, ...]
    calls: tuple[ArchitectureCallRule, ...] = ()
    forbidden_under_locks: tuple[ArchitectureForbiddenUnderLockCallRule, ...] = ()
    lock_orders: tuple[ArchitectureLockOrderRule, ...] = ()
    assignments: tuple[ArchitectureAssignmentRule, ...] = ()

    @property
    def call_rules(self) -> tuple[ArchitectureCallRule, ...]:
        """Compatibility alias for callers that name the rule category explicitly."""

        return self.calls

    @property
    def assignment_rules(self) -> tuple[ArchitectureAssignmentRule, ...]:
        """Compatibility alias for callers that name the rule category explicitly."""

        return self.assignments

    @property
    def forbidden_call_rules(self) -> tuple[ArchitectureForbiddenUnderLockCallRule, ...]:
        """Compatibility alias for the forbidden-under-lock call category."""

        return self.forbidden_under_locks

    @property
    def forbidden_calls(self) -> tuple[ArchitectureForbiddenUnderLockCallRule, ...]:
        """Short compatibility alias for forbidden-under-lock calls."""

        return self.forbidden_under_locks


@dataclass(frozen=True)
class ArchitectureFinding:
    rule_id: str
    severity: str
    path: str
    line: int
    message: str
    snippet: str
    regex: str
    lock: str = ""
    outer_locks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArchitectureScanResult:
    findings: tuple[ArchitectureFinding, ...]
    scanned_files: int
    rules_checked: int


_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
}
