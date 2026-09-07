from __future__ import annotations

from types import SimpleNamespace

from keyrgb.tray.controllers.secondary_static_scene import apply_secondary_static_fallback


def test_static_fallback_restores_software_targets_before_profile_scene(monkeypatch) -> None:
    from keyrgb.tray.controllers import secondary_static_scene, software_target_controller

    calls: list[str] = []
    tray = SimpleNamespace()
    monkeypatch.setattr(
        software_target_controller,
        "software_effect_target_routes_aux_devices",
        lambda selected: selected is tray,
    )
    monkeypatch.setattr(
        software_target_controller,
        "restore_secondary_software_targets",
        lambda selected: calls.append("restore") if selected is tray else None,
    )
    monkeypatch.setattr(
        secondary_static_scene,
        "apply_secondary_static_scene",
        lambda selected: calls.append("scene") or selected is tray,
    )

    assert apply_secondary_static_fallback(tray) is True
    assert calls == ["restore", "scene"]


def test_static_fallback_skips_software_restore_when_auxiliaries_are_not_routed(monkeypatch) -> None:
    from keyrgb.tray.controllers import secondary_static_scene, software_target_controller

    restore_calls: list[object] = []
    tray = SimpleNamespace()
    monkeypatch.setattr(software_target_controller, "software_effect_target_routes_aux_devices", lambda _tray: False)
    monkeypatch.setattr(software_target_controller, "restore_secondary_software_targets", restore_calls.append)
    monkeypatch.setattr(secondary_static_scene, "apply_secondary_static_scene", lambda selected: selected is tray)

    assert apply_secondary_static_fallback(tray) is True
    assert restore_calls == []
