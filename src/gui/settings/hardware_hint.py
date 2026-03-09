from __future__ import annotations


def extract_unsupported_rgb_controllers_hint(backends_snapshot: dict) -> str:
    """Best-effort extraction of an actionable 'unsupported controller' hint.

    The input is expected to be a diagnostics snapshot dict.
    """

    probes = backends_snapshot.get("probes")
    if not isinstance(probes, list):
        return ""

    unsupported: list[str] = []
    experimental_disabled: list[str] = []
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

        if "unsupported by ite8291r3 backend" in reason.lower():
            unsupported.append(f"{vid}:{pid}")
        if pid.lower() == "0x8910" and "experimental backend disabled" in reason.lower():
            experimental_disabled.append(f"{vid}:{pid}")

    if experimental_disabled:
        joined = ", ".join(experimental_disabled)
        return f"Detected experimental RGB controller(s): {joined}. Enable Experimental backends in Settings to try the ite8910 backend."

    if not unsupported:
        return ""

    joined = ", ".join(unsupported)
    return f"Detected unsupported RGB controller(s): {joined} (Tier 3 / Fusion 2)."
