from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ._architecture_validation_load import load_architecture_rules as _load_architecture_rules
from ._architecture_validation_models import ArchitectureRule, ArchitectureScanResult
from ._architecture_validation_scan import scan_architecture as _scan_architecture


def load_architecture_rules(config_path: Path) -> list[ArchitectureRule]:
    return _load_architecture_rules(config_path)


def scan_architecture(root: Path, rules: Iterable[ArchitectureRule]) -> ArchitectureScanResult:
    return _scan_architecture(root, rules)
