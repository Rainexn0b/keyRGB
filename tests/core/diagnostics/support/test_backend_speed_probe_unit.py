from __future__ import annotations

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.diagnostics.support import (
    ITE8910_SPEED_PROBE_KEY,
    build_backend_speed_probe_plan,
    build_backend_speed_probe_plans,
)


def test_build_backend_speed_probe_plan_for_ite8910() -> None:
    plan = build_backend_speed_probe_plan("ite8910")

    assert isinstance(plan, dict)
    assert plan["key"] == ITE8910_SPEED_PROBE_KEY
    assert plan["backend"] == "ite8910"
    assert plan["effect_name"] == "spectrum_cycle"
    assert plan["requested_ui_speeds"] == [1, 3, 5, 7, 10]
    assert [sample["raw_speed"] for sample in plan["samples"]] == [1, 3, 5, 7, 10]


def test_build_backend_speed_probe_plans_filters_to_supported_backends() -> None:
    plans = build_backend_speed_probe_plans(
        backends_snapshot={
            "selected": "ite8910",
            "probes": [
                {"name": "ite8910", "available": True},
                {"name": "sysfs-leds", "available": True},
            ],
        }
    )

    assert len(plans) == 1
    assert plans[0]["backend"] == "ite8910"
