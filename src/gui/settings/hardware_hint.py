from __future__ import annotations

from src.core.backends.policy import experimental_evidence_label


def extract_unsupported_rgb_controllers_hint(backends_snapshot: dict) -> str:
    """Best-effort extraction of an actionable 'unsupported controller' hint.

    The input is expected to be a diagnostics snapshot dict.
    """

    probes = backends_snapshot.get("probes")
    if not isinstance(probes, list):
        return ""

    family_ids_with_experimental_path: set[str] = set()
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        ids = probe.get("identifiers")
        if not isinstance(ids, dict):
            continue
        vid = ids.get("usb_vid")
        pid = ids.get("usb_pid")
        if not (isinstance(vid, str) and isinstance(pid, str)):
            continue
        if str(probe.get("stability") or "").strip().lower() == "experimental":
            family_ids_with_experimental_path.add(f"{vid}:{pid}".lower())

    unsupported: list[str] = []
    experimental_disabled: list[str] = []
    experimental_backend_names: list[str] = []
    research_backed_disabled = False
    for probe in probes:
        if not isinstance(probe, dict):
            continue

        reason = str(probe.get("reason") or "")
        ids = probe.get("identifiers")
        if not isinstance(ids, dict):
            continue

        vid = ids.get("usb_vid")
        pid = ids.get("usb_pid")
        if not (isinstance(vid, str) and isinstance(pid, str)):
            continue

        key = f"{vid}:{pid}".lower()

        if "unsupported by ite8291r3 backend" in reason.lower() and key not in family_ids_with_experimental_path:
            unsupported.append(f"{vid}:{pid}")
        if "experimental backend disabled" in reason.lower():
            experimental_disabled.append(f"{vid}:{pid}")
            backend_name = str(probe.get("name") or "").strip()
            if backend_name:
                experimental_backend_names.append(backend_name)
            evidence_label = experimental_evidence_label(probe.get("experimental_evidence"))
            if evidence_label == "research-backed":
                research_backed_disabled = True

    if experimental_disabled:
        joined = ", ".join(experimental_disabled)
        label = "research-backed experimental RGB controller(s)" if research_backed_disabled else "experimental RGB controller(s)"
        backend_names = sorted({name for name in experimental_backend_names if name})
        if backend_names:
            if len(backend_names) == 1:
                backend_text = f"the {backend_names[0]} backend"
            else:
                backend_text = "these backends: " + ", ".join(backend_names)
        else:
            backend_text = "the matching backend"
        return f"Detected {label}: {joined}. Enable Experimental backends in Settings to try {backend_text}."

    if not unsupported:
        return ""

    joined = ", ".join(unsupported)
    return f"Detected unsupported RGB controller(s): {joined} (Tier 3 / Fusion 2)."
