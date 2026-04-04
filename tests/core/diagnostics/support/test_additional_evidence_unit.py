from __future__ import annotations

from types import SimpleNamespace

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.core.diagnostics.support.evidence as evidence


def test_build_additional_evidence_plan_for_attention_candidate() -> None:
    plan = evidence.build_additional_evidence_plan(
        {
            "candidates": [
                {
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "status": "known_dormant",
                    "hidraw_nodes": ["/dev/hidraw1"],
                    "hidraw_descriptor_sizes": [],
                }
            ]
        }
    )

    assert plan["usb_id"] == "048d:7001"
    assert [item["key"] for item in plan["automated"]] == ["lsusb_verbose", "hid_descriptor_dump"]


def test_collect_additional_evidence_runs_direct_and_privileged(monkeypatch) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(evidence.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        evidence.shutil,
        "which",
        lambda name: {
            "lsusb": "/usr/bin/lsusb",
            "usbhid-dump": "/usr/bin/usbhid-dump",
            "pkexec": "/usr/bin/pkexec",
        }.get(name),
    )

    def _run(argv, check=False, capture_output=True, text=True):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(evidence.subprocess, "run", _run)

    payload = evidence.collect_additional_evidence(
        {
            "candidates": [
                {
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "status": "known_dormant",
                    "hidraw_nodes": ["/dev/hidraw1"],
                    "hidraw_descriptor_sizes": [],
                }
            ]
        },
        allow_privileged=True,
    )

    assert calls[0] == ["lsusb", "-v", "-d", "048d:7001"]
    assert calls[1] == ["/usr/bin/pkexec", "usbhid-dump", "-d", "048d:7001", "-e", "descriptor"]
    assert payload["captures"]["lsusb_verbose"]["ok"] is True
    assert payload["captures"]["hid_descriptor_dump"]["via"] == "pkexec"
