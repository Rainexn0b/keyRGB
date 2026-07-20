from __future__ import annotations

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.gui.windows._support._support_window_backend_probe as support_window_backend_probe
import src.gui.windows.support as support_window
from tests.gui.windows._support_window_test_fakes import make_window as _make_window


def test_probe_config_snapshot_returns_typed_value_object() -> None:
    class _FakeConfig:
        def __init__(self) -> None:
            self._effect = "wave"
            self._speed = 13
            self._settings = {"effect_speeds": {"wave": 4}}

        @property
        def effect(self) -> str:
            return self._effect

        @property
        def speed(self) -> int:
            return self._speed

    config = _FakeConfig()

    snapshot = support_window.support_jobs._probe_config_snapshot(config)
    config._settings["effect_speeds"]["wave"] = 9

    assert isinstance(snapshot, support_window_backend_probe.ProbeConfigSnapshot)
    assert snapshot.effect == "wave"
    assert snapshot.speed == 10
    assert snapshot.effect_speeds == {"wave": 4}


def test_restore_probe_config_accepts_legacy_snapshot_dict_and_clears_empty_effect_speeds() -> None:
    class _FakeConfig:
        def __init__(self) -> None:
            self._effect = "wave"
            self._speed = 1
            self._settings = {"effect_speeds": {"wave": 8}}
            self.calls: list[tuple[object, ...]] = []

        @property
        def effect(self) -> str:
            return self._effect

        @effect.setter
        def effect(self, value: str) -> None:
            self._effect = str(value)
            self.calls.append(("effect", str(value)))

        @property
        def speed(self) -> int:
            return self._speed

        @speed.setter
        def speed(self, value: int) -> None:
            self._speed = int(value)
            self.calls.append(("speed", int(value)))

        def _save(self) -> None:
            self.calls.append(("save_effect_speeds", dict(self._settings.get("effect_speeds", {}))))

    config = _FakeConfig()

    support_window.support_jobs._restore_probe_config(
        config,
        snapshot={"effect": "color_cycle", "speed": 9, "effect_speeds": {}},
    )

    assert "effect_speeds" not in config._settings
    assert config.calls == [
        ("save_effect_speeds", {}),
        ("speed", 9),
        ("effect", "color_cycle"),
    ]


def test_run_backend_speed_probe_records_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8910_speed", "backend": "ite8910_perkey", "effect_name": "spectrum_cycle", "selection_effect_name": "hw:spectrum_cycle", "selection_menu_path": "Hardware Effects -> Spectrum Cycle", "requested_ui_speeds": [1, 3], "samples": [{"ui_speed": 1, "payload_speed": 1, "raw_speed_hex": "0x01"}] , "instructions": ["Do the thing"], "observation_prompt": "Notes?"}]}}'
    )
    responses = iter([True, False])
    showinfo_calls: list[str] = []

    class _FakeConfig:
        def __init__(self) -> None:
            self._effect = "color_cycle"
            self._speed = 9
            self._settings = {"effect_speeds": {"spectrum_cycle": 4, "color_cycle": 9}}

        @property
        def effect(self) -> str:
            return self._effect

        @effect.setter
        def effect(self, value: str) -> None:
            self._effect = str(value)

        @property
        def speed(self) -> int:
            return self._speed

        @speed.setter
        def speed(self, value: int) -> None:
            self._speed = int(value)

        def set_effect_speed(self, effect_name: str, speed: int) -> None:
            self._settings.setdefault("effect_speeds", {})[str(effect_name)] = int(speed)

        def _save(self) -> None:
            return

    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: True)
    monkeypatch.setattr(
        support_window.support_jobs,
        "_show_probe_message_dialog",
        lambda _window, *, title, message, **_kwargs: showinfo_calls.append(str(message)) or True,
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_choice_dialog",
        lambda _window, *, title, prompt, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_notes_dialog",
        lambda _window, *, title, prompt, **_kwargs: "1 and 3 looked too close",
    )
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(support_window, "Config", _FakeConfig)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.support_jobs.time, "sleep", lambda _seconds: None)

    window.run_backend_speed_probe(prompt=True)

    assert window._supplemental_evidence is not None
    backend_probes = window._supplemental_evidence.get("backend_probes")
    assert isinstance(backend_probes, dict)
    probe = backend_probes["ite8910_speed"]
    assert probe["backend"] == "ite8910_perkey"
    assert probe["selection_effect_name"] == "hw:spectrum_cycle"
    assert probe["execution_mode"] == "auto"
    assert probe["automation"]["step_duration_s"] == 2.5
    assert probe["automation"]["settle_duration_s"] == 0.5
    assert probe["observation"]["distinct_steps"] is False
    assert probe["observation"]["notes"] == "1 and 3 looked too close"
    assert window.status_label.options["text"] == "Backend speed probe recorded"
    assert showinfo_calls
    assert "temporarily switch the tray to the probe effect" in showinfo_calls[0]
    assert "Each speed will stay active for about 2.5 seconds" in showinfo_calls[0]


def test_run_backend_speed_probe_can_auto_run_via_tray_config(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8291r3_speed", "backend": "ite8291r3_perkey", "effect_name": "wave", "selection_effect_name": "wave", "selection_menu_path": "Hardware Effects -> Wave", "requested_ui_speeds": [1, 3], "samples": [{"ui_speed": 1, "payload_speed": 10, "raw_speed_hex": "0x0a"}] , "instructions": ["Do the thing"], "observation_prompt": "Notes?"}]}}'
    )
    responses = iter([True, True])
    showinfo_calls: list[str] = []
    sleep_calls: list[float] = []

    class _FakeConfig:
        last_instance = None

        def __init__(self) -> None:
            type(self).last_instance = self
            self._effect = "color_cycle"
            self._speed = 9
            self._settings = {"effect_speeds": {"wave": 4, "color_cycle": 9}}
            self.calls: list[tuple[object, ...]] = []

        @property
        def effect(self) -> str:
            return self._effect

        @effect.setter
        def effect(self, value: str) -> None:
            self._effect = str(value)
            self.calls.append(("effect", str(value)))

        @property
        def speed(self) -> int:
            return self._speed

        @speed.setter
        def speed(self, value: int) -> None:
            self._speed = int(value)
            self.calls.append(("speed", int(value)))

        def set_effect_speed(self, effect_name: str, speed: int) -> None:
            self._settings.setdefault("effect_speeds", {})[str(effect_name)] = int(speed)
            self.calls.append(("set_effect_speed", str(effect_name), int(speed)))

        def _save(self) -> None:
            self.calls.append(("save_effect_speeds", dict(self._settings.get("effect_speeds", {}))))

    monkeypatch.setenv("KEYRGB_TRAY_PID", "1234")
    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: True)
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_choice_dialog",
        lambda _window, *, title, prompt, **_kwargs: next(responses),
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_show_probe_message_dialog",
        lambda _window, *, title, message, **_kwargs: showinfo_calls.append(str(message)) or True,
    )
    monkeypatch.setattr(
        support_window.support_jobs,
        "_ask_probe_notes_dialog",
        lambda _window, *, title, prompt, **_kwargs: "looked distinct",
    )
    monkeypatch.setattr(
        support_window,
        "build_issue_report_with_evidence",
        lambda *, diagnostics, discovery, supplemental_evidence=None: {
            "markdown": "issue draft",
            "issue_url": "https://example.invalid",
        },
    )
    monkeypatch.setattr(support_window, "Config", _FakeConfig)
    monkeypatch.setattr(support_window, "run_in_thread", lambda root, work, on_done: on_done(work()))
    monkeypatch.setattr(support_window.support_jobs.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    window.run_backend_speed_probe(prompt=True)

    probe = window._supplemental_evidence["backend_probes"]["ite8291r3_speed"]
    assert probe["execution_mode"] == "auto"
    assert probe["automation"]["step_duration_s"] == 2.5
    assert probe["automation"]["settle_duration_s"] == 0.5
    assert probe["observation"]["distinct_steps"] is True
    assert probe["observation"]["notes"] == "looked distinct"
    assert probe["automation"]["applied_ui_speeds"] == [1, 3]
    assert sleep_calls == [0.5, 2.5, 2.5, 0.5]
    assert _FakeConfig.last_instance is not None
    assert _FakeConfig.last_instance.calls == [
        ("effect", "wave"),
        ("set_effect_speed", "wave", 1),
        ("speed", 1),
        ("set_effect_speed", "wave", 3),
        ("speed", 3),
        ("save_effect_speeds", {"wave": 4, "color_cycle": 9}),
        ("speed", 9),
        ("effect", "color_cycle"),
    ]
    assert showinfo_calls
    assert "temporarily switch the tray to the probe effect" in showinfo_calls[0]
    assert "Each speed will stay active for about 2.5 seconds" in showinfo_calls[0]


def test_run_backend_speed_probe_builds_job_inputs_without_changing_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _make_window()
    seen: dict[str, object] = {}

    def _capture(window_arg, **kwargs) -> None:
        seen["window"] = window_arg
        seen.update(kwargs)

    monkeypatch.setenv("KEYRGB_TRAY_PID", "4242")
    monkeypatch.setattr(support_window.support_jobs, "run_backend_speed_probe", _capture)

    window.run_backend_speed_probe(prompt=False)

    assert seen["window"] is window
    assert seen["prompt"] is False
    assert callable(seen["current_backend_speed_probe_plan_fn"])
    assert seen["messagebox"] is support_window.messagebox
    assert seen["tk_runtime_errors"] == support_window._TK_RUNTIME_ERRORS
    assert seen["run_in_thread"] is support_window.run_in_thread
    assert seen["config_cls"] is support_window.Config
    assert seen["tray_pid"] == "4242"
    assert seen["tk"] is support_window.tk
    assert seen["ttk"] is support_window.ttk
    assert seen["scrolledtext"] is support_window.scrolledtext


def test_run_backend_speed_probe_requires_running_tray(monkeypatch: pytest.MonkeyPatch) -> None:
    window = _make_window(
        diagnostics_json='{"backends": {"guided_speed_probes": [{"key": "ite8291r3_speed", "backend": "ite8291r3_perkey", "effect_name": "wave"}]}}'
    )

    monkeypatch.setattr(support_window.support_jobs, "_tray_process_alive", lambda _tray_pid: False)

    window.run_backend_speed_probe(prompt=False)

    assert window._supplemental_evidence is None
    assert window.status_label.options["text"] == "Backend speed probe requires the running tray session"
