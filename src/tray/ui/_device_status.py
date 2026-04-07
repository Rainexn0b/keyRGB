from __future__ import annotations

from typing import Any

from src.core.backends.policy import (
    experimental_evidence_for_backend,
    experimental_evidence_label,
    stability_for_backend,
)


def format_hex_id(val: str) -> str:
    s = str(val or "").strip().lower() if val is not None else ""
    if s.startswith("0x"):
        s = s[2:]
    return s


def backend_display_name(backend_name: str) -> str:
    if backend_name == "sysfs-leds":
        return "Kernel Driver"
    if backend_name == "ite8291r3":
        return "ITE 8291r3 (USB)"
    if backend_name == "ite8910":
        return "ITE 8910 (USB)"
    if backend_name == "ite8297":
        return "ITE 8297 (USB)"
    return backend_name


def backend_status_suffix(backend: Any) -> str:
    if backend is None:
        return ""

    if stability_for_backend(backend).value != "experimental":
        return ""

    parts = ["experimental"]
    evidence_label = experimental_evidence_label(experimental_evidence_for_backend(backend))
    if evidence_label:
        parts.append(evidence_label)

    return f" [{', '.join(parts)}]"


def secondary_status_suffix(status: str) -> str:
    if status == "supported":
        return ""
    if status == "experimental_disabled":
        return " [experimental disabled]"
    if status == "known_dormant":
        return " [detected]"
    if status == "known_unavailable":
        return " [unavailable]"
    if status == "unrecognized_ite":
        return " [unrecognized]"
    return f" [{status}]" if status else ""
