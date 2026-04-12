from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.tray.app._startup import migrate_builtin_profile_brightness_best_effort


def test_migrate_builtin_profile_brightness_best_effort_runs_migration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.profile import profiles as core_profiles

    calls: list[object] = []
    config = SimpleNamespace()

    monkeypatch.setattr(core_profiles, "migrate_builtin_profile_brightness", lambda cfg: calls.append(cfg))

    migrate_builtin_profile_brightness_best_effort(config)

    assert calls == [config]


def test_migrate_builtin_profile_brightness_best_effort_swallows_recoverable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(
        core_profiles,
        "migrate_builtin_profile_brightness",
        lambda _cfg: (_ for _ in ()).throw(RuntimeError("migration failed")),
    )

    migrate_builtin_profile_brightness_best_effort(SimpleNamespace())


def test_migrate_builtin_profile_brightness_best_effort_propagates_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.core.profile import profiles as core_profiles

    monkeypatch.setattr(
        core_profiles,
        "migrate_builtin_profile_brightness",
        lambda _cfg: (_ for _ in ()).throw(AssertionError("unexpected migration bug")),
    )

    with pytest.raises(AssertionError, match="unexpected migration bug"):
        migrate_builtin_profile_brightness_best_effort(SimpleNamespace())