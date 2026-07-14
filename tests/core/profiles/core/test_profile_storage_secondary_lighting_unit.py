from __future__ import annotations

from src.core.profile import profiles


def test_profile_paths_include_secondary_lighting(profile_paths_factory, temp_profile_dir) -> None:
    paths = profile_paths_factory(temp_profile_dir)

    assert paths.secondary_lighting == temp_profile_dir / "secondary_lighting.json"


def test_missing_secondary_lighting_is_distinguishable_from_explicit_empty(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)

    assert profiles.load_secondary_lighting("test_profile") is None

    saved = profiles.save_secondary_lighting({"version": 1, "areas": {}}, "test_profile")

    assert saved == {"version": 1, "areas": {}}
    assert profiles.load_secondary_lighting("test_profile") == {"version": 1, "areas": {}}


def test_secondary_lighting_normalizes_rgb_and_enabled_values(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)

    profiles.write_json_atomic(
        paths.secondary_lighting,
        {
            "version": 99,
            "areas": {
                "ite8258_chassis_logo": {"enabled": 1, "color": [300, -2, 17], "brightness": 120},
                "ite8258_chassis_neon": {"enabled": 0, "color": [1.9, 2.1, 3.8], "brightness": -4},
                "ite8258_chassis_vent": {"enabled": "yes", "color": [1, 2], "brightness": "full"},
            },
        },
    )

    assert profiles.load_secondary_lighting("test_profile") == {
        "version": 1,
        "areas": {
            "ite8258_chassis_logo": {"enabled": True, "color": [255, 0, 17], "brightness": 100},
            "ite8258_chassis_neon": {"enabled": False, "color": [1, 2, 3], "brightness": 0},
            "ite8258_chassis_vent": {},
        },
    }


def test_secondary_lighting_preserves_unknown_routes_top_level_and_entry_fields(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)

    payload = {
        "version": 1,
        "future_component": {"schema": 7},
        "areas": {
            "future_route": {
                "enabled": True,
                "color": [4, 5, 6],
                "future_entry_field": "keep-me",
            },
            "ite8258_chassis_logo": {
                "enabled": True,
                "color": [9, 8, 7],
                "future_entry_field": {"nested": True},
            },
        },
    }
    profiles.write_json_atomic(paths.secondary_lighting, payload)

    loaded = profiles.load_secondary_lighting("test_profile")
    assert loaded is not None
    loaded["areas"]["ite8258_chassis_logo"]["color"] = [1, 2, 3]  # type: ignore[index]

    profiles.save_secondary_lighting(loaded, "test_profile")

    saved = profiles.load_secondary_lighting("test_profile")
    assert saved is not None
    assert saved["future_component"] == {"schema": 7}
    assert saved["areas"]["future_route"]["future_entry_field"] == "keep-me"  # type: ignore[index]
    assert saved["areas"]["ite8258_chassis_logo"] == {
        "enabled": True,
        "color": [1, 2, 3],
        "future_entry_field": {"nested": True},
    }  # type: ignore[index]


def test_unavailable_route_state_round_trips_without_requiring_route_registration(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)

    payload = {
        "version": 1,
        "areas": {
            "disconnected_future_route": {"enabled": True, "color": [12, 34, 56]},
        },
    }

    profiles.save_secondary_lighting(payload, "test_profile")

    assert profiles.load_secondary_lighting("test_profile") == payload


def test_secondary_lighting_save_uses_profile_atomic_writer(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)
    writes: list[tuple[object, object]] = []
    monkeypatch.setattr(profiles, "write_json_atomic", lambda path, payload: writes.append((path, payload)))

    result = profiles.save_secondary_lighting(
        {"version": 1, "areas": {"logo": {"enabled": True, "color": [255, 0, 0]}}},
        "test_profile",
    )

    assert writes == [(paths.secondary_lighting, result)]


def test_update_secondary_lighting_area_preserves_other_routes_and_unknown_fields(
    profile_paths_factory,
    temp_profile_dir,
    monkeypatch,
) -> None:
    paths = profile_paths_factory(temp_profile_dir)
    monkeypatch.setattr(profiles, "paths_for", lambda _name=None: paths)
    profiles.save_secondary_lighting(
        {
            "version": 1,
            "future": "keep",
            "areas": {
                "lightbar": {"enabled": True, "color": [1, 2, 3], "vendor": 7},
                "mouse": {"enabled": False, "color": [4, 5, 6]},
            },
        },
        "test_profile",
    )

    result = profiles.update_secondary_lighting_area(
        "lightbar",
        {"brightness": 35, "enabled": False},
        "test_profile",
    )

    assert result == {
        "version": 1,
        "future": "keep",
        "areas": {
            "lightbar": {
                "enabled": False,
                "color": [1, 2, 3],
                "vendor": 7,
                "brightness": 35,
            },
            "mouse": {"enabled": False, "color": [4, 5, 6]},
        },
    }
