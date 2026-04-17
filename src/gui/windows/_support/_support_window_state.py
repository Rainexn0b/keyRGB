#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SupportSessionState:
    diagnostics_json: str = ""
    discovery_json: str = ""
    supplemental_evidence: dict[str, object] | None = None
    issue_report: dict[str, object] | None = None
    capture_prompt_key: str = ""
    backend_probe_prompt_key: str = ""
