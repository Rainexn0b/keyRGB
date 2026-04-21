from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

import src.gui.tcc._profile_actions as profile_actions


class _WriteError(Exception):
    pass


def _recorder() -> tuple[list[str], list[str], Any, Any]:
    statuses: list[str] = []
    refreshes: list[str] = []

    def set_status(msg: str) -> None:
        statuses.append(msg)

    def refresh() -> None:
        refreshes.append("refresh")

    return statuses, refreshes, set_status, refresh


def test_create_profile_cancel_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: None)
    create_calls: list[str] = []
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "create_custom_profile", lambda _name: create_calls.append("called"))

    profile_actions.create_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        write_errors=(_WriteError,),
    )

    assert create_calls == []
    assert statuses == []
    assert refreshes == []


def test_create_profile_blank_name_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "   ")
    create_calls: list[str] = []
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "create_custom_profile", lambda _name: create_calls.append("called"))

    profile_actions.create_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        write_errors=(_WriteError,),
    )

    assert create_calls == []
    assert statuses == []
    assert refreshes == []


def test_create_profile_success_calls_create_status_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "  My Profile  ")
    created_names: list[str] = []
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "create_custom_profile", lambda name: created_names.append(name))

    profile_actions.create_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        write_errors=(_WriteError,),
    )

    assert created_names == ["My Profile"]
    assert statuses == ["\u2713 Created"]
    assert refreshes == ["refresh"]


def test_create_profile_write_error_logs_and_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "My Profile")
    err = _WriteError("disk full")
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "create_custom_profile",
        lambda _name: (_ for _ in ()).throw(err),
    )

    log_calls: list[dict[str, Any]] = []

    def fake_log_throttled(logger, key: str, *, interval_s: float, level: int, msg: str, exc=None) -> bool:
        log_calls.append({"key": key, "msg": msg, "exc": exc, "level": level, "interval": interval_s})
        return True

    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions, "log_throttled", fake_log_throttled)
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))

    profile_actions.create_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        write_errors=(_WriteError,),
    )

    assert len(log_calls) == 1
    assert log_calls[0]["key"] == "tcc_profiles.create_custom_profile"
    assert log_calls[0]["exc"] is err
    assert errors == [("Create failed", "disk full")]
    assert statuses == []
    assert refreshes == []


def test_duplicate_profile_builtin_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="balanced", name="Balanced")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: True)
    ask_calls: list[str] = []
    monkeypatch.setattr(
        profile_actions.simpledialog,
        "askstring",
        lambda *_args, **_kwargs: ask_calls.append("asked") or "dup",
    )

    profile_actions.duplicate_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert ask_calls == []
    assert statuses == []
    assert refreshes == []


@pytest.mark.parametrize("answer", [None, "   "])
def test_duplicate_profile_cancel_or_blank_short_circuit(monkeypatch: pytest.MonkeyPatch, answer: str | None) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: answer)
    duplicate_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "duplicate_custom_profile",
        lambda profile_id, name: duplicate_calls.append((profile_id, name)),
    )

    profile_actions.duplicate_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert duplicate_calls == []
    assert statuses == []
    assert refreshes == []


def test_duplicate_profile_success(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "  Duplicated  ")
    duplicate_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "duplicate_custom_profile",
        lambda profile_id, name: duplicate_calls.append((profile_id, name)),
    )

    profile_actions.duplicate_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert duplicate_calls == [("custom-1", "Duplicated")]
    assert statuses == ["\u2713 Duplicated"]
    assert refreshes == ["refresh"]


def test_duplicate_profile_write_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "Dup")
    err = _WriteError("cannot write")
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "duplicate_custom_profile",
        lambda _profile_id, _name: (_ for _ in ()).throw(err),
    )

    log_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "log_throttled", lambda *_args, **_kwargs: log_calls.append("log") or True)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))

    profile_actions.duplicate_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert log_calls == ["log"]
    assert errors == [("Duplicate failed", "cannot write")]
    assert statuses == []
    assert refreshes == []


def test_rename_profile_builtin_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="performance", name="Performance")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: True)
    ask_calls: list[str] = []
    monkeypatch.setattr(
        profile_actions.simpledialog,
        "askstring",
        lambda *_args, **_kwargs: ask_calls.append("asked") or "new",
    )

    profile_actions.rename_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert ask_calls == []
    assert statuses == []
    assert refreshes == []


@pytest.mark.parametrize("answer", [None, "   "])
def test_rename_profile_cancel_or_blank_short_circuit(monkeypatch: pytest.MonkeyPatch, answer: str | None) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Old")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: answer)
    rename_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "rename_custom_profile",
        lambda profile_id, name: rename_calls.append((profile_id, name)),
    )

    profile_actions.rename_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert rename_calls == []
    assert statuses == []
    assert refreshes == []


def test_rename_profile_success(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Old")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "  New Name  ")
    rename_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "rename_custom_profile",
        lambda profile_id, name: rename_calls.append((profile_id, name)),
    )

    profile_actions.rename_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert rename_calls == [("custom-1", "New Name")]
    assert statuses == ["\u2713 Renamed"]
    assert refreshes == ["refresh"]


def test_rename_profile_write_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Old")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.simpledialog, "askstring", lambda *_args, **_kwargs: "New")
    err = _WriteError("no permission")
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "rename_custom_profile",
        lambda _profile_id, _name: (_ for _ in ()).throw(err),
    )

    log_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "log_throttled", lambda *_args, **_kwargs: log_calls.append("log") or True)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))

    profile_actions.rename_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert log_calls == ["log"]
    assert errors == [("Rename failed", "no permission")]
    assert statuses == []
    assert refreshes == []


def test_delete_profile_internal_id_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="__builtin", name="Builtin")
    ask_calls: list[str] = []
    monkeypatch.setattr(
        profile_actions.messagebox,
        "askyesno",
        lambda *_args, **_kwargs: ask_calls.append("asked") or True,
    )

    profile_actions.delete_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert ask_calls == []
    assert statuses == []
    assert refreshes == []


def test_delete_profile_confirmation_no_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    delete_calls: list[str] = []
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "delete_custom_profile", lambda _id: delete_calls.append("called"))

    profile_actions.delete_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert delete_calls == []
    assert statuses == []
    assert refreshes == []


def test_delete_profile_success(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    delete_calls: list[str] = []
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "delete_custom_profile", lambda profile_id: delete_calls.append(profile_id))

    profile_actions.delete_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert delete_calls == ["custom-1"]
    assert statuses == ["\u2713 Deleted"]
    assert refreshes == ["refresh"]


def test_delete_profile_write_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions.messagebox, "askyesno", lambda *_args, **_kwargs: True)
    err = _WriteError("busy")
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "delete_custom_profile",
        lambda _profile_id: (_ for _ in ()).throw(err),
    )
    log_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "log_throttled", lambda *_args, **_kwargs: log_calls.append("log") or True)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))

    profile_actions.delete_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert log_calls == ["log"]
    assert errors == [("Delete failed", "busy")]
    assert statuses == []
    assert refreshes == []


def test_edit_profile_builtin_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="quiet", name="Quiet")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: True)
    editor_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "open_profile_json_editor", lambda *_args, **_kwargs: editor_calls.append("open"))

    profile_actions.edit_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert editor_calls == []
    assert statuses == []
    assert refreshes == []


def test_edit_profile_payload_fetch_write_error_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    err = _WriteError("dbus timeout")
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "get_custom_profile_payload",
        lambda _profile_id: (_ for _ in ()).throw(err),
    )
    log_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "log_throttled", lambda *_args, **_kwargs: log_calls.append("log") or True)
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))
    editor_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "open_profile_json_editor", lambda *_args, **_kwargs: editor_calls.append("open"))

    profile_actions.edit_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert log_calls == ["log"]
    assert errors == [("Edit failed", "Could not load editable profile payload from tccd.")]
    assert editor_calls == []
    assert statuses == []
    assert refreshes == []


def test_edit_profile_non_dict_payload_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "get_custom_profile_payload", lambda _profile_id: ["not", "dict"])

    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(profile_actions.messagebox, "showerror", lambda title, message: errors.append((str(title), str(message))))
    editor_calls: list[str] = []
    monkeypatch.setattr(profile_actions, "open_profile_json_editor", lambda *_args, **_kwargs: editor_calls.append("open"))

    profile_actions.edit_profile(
        object(),
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert errors == [("Edit failed", "Could not load editable profile payload from tccd.")]
    assert editor_calls == []
    assert statuses == []
    assert refreshes == []


def test_edit_profile_success_opens_editor_and_callbacks_save_status_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses, refreshes, set_status, refresh = _recorder()
    profile = SimpleNamespace(id="custom-1", name="Custom")
    payload = {"id": "custom-1", "limit": 42}
    monkeypatch.setattr(profile_actions, "is_builtin_profile_id", lambda _id: False)
    monkeypatch.setattr(profile_actions.tcc_power_profiles, "get_custom_profile_payload", lambda _profile_id: payload)

    update_calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        profile_actions.tcc_power_profiles,
        "update_custom_profile",
        lambda profile_id, obj: update_calls.append((profile_id, obj)),
    )

    editor_invocations: list[dict[str, Any]] = []

    def fake_open_editor(root, *, profile_name, payload, on_save, on_saved) -> None:
        editor_invocations.append(
            {
                "root": root,
                "profile_name": profile_name,
                "payload": payload,
                "on_save": on_save,
                "on_saved": on_saved,
            }
        )

    monkeypatch.setattr(profile_actions, "open_profile_json_editor", fake_open_editor)

    root = object()
    profile_actions.edit_profile(
        root,
        logger=logging.getLogger("test"),
        set_status=set_status,
        refresh=refresh,
        profile=profile,
        write_errors=(_WriteError,),
    )

    assert len(editor_invocations) == 1
    call = editor_invocations[0]
    assert call["root"] is root
    assert call["profile_name"] == "Custom"
    assert call["payload"] == payload

    saved_payload = {"id": "custom-1", "limit": 55}
    call["on_save"](saved_payload)
    call["on_saved"]()

    assert update_calls == [("custom-1", saved_payload)]
    assert statuses == ["\u2713 Saved"]
    assert refreshes == ["refresh"]
