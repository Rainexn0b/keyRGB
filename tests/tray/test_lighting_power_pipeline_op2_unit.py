"""OP-2 regressions: menu/power is_off writes through DeckPipeline.

Covers the remaining SWP-4 seam:

* public ``lighting_controller`` entrypoints are decided by ``DeckPipeline``
  using ``MANUAL_ON``/``MANUAL_OFF``/``POWER_OFF``/``POWER_RESUME``;
* bare ``tray.is_off=True`` with no forced-off flag still restores via the
  narrow override (``hardware_apply_deferred`` stays false);
* a restoring leaf publishes ``DeckState.RESTORING`` before it blocks on its
  fade, then ``LIT``/``DIM_TEMP`` on success or the origin on failure;
* a second wake intent while ``RESTORING`` coalesces.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from keyrgb.tray.deck_state import DeckState, SleepWakeIntentKind
from tests.tray.fakes import make_owner_backed_mock_tray


def _bare_is_off_tray(**overrides):
    tray = make_owner_backed_mock_tray(is_off=True, **overrides)
    # Ensure no forced-off owner flags and no native sleep latch.
    tray.tray_idle_power_state.controller_sleep_off = False
    tray.tray_idle_power_state.user_forced_off = False
    tray.tray_idle_power_state.power_forced_off = False
    tray.tray_idle_power_state.idle_forced_off = False
    # Legacy mirrors for duck-typed checks.
    tray._user_forced_off = False
    tray._power_forced_off = False
    tray._idle_forced_off = False
    return tray


class TestPublicEntrypointsCallOnePipelineDecision:
    @pytest.mark.parametrize(
        "entrypoint,intent_kind",
        [
            ("turn_on", SleepWakeIntentKind.MANUAL_ON),
            ("turn_off", SleepWakeIntentKind.MANUAL_OFF),
            ("power_turn_off", SleepWakeIntentKind.POWER_OFF),
            ("power_restore", SleepWakeIntentKind.POWER_RESUME),
        ],
    )
    def test_public_entrypoints_call_one_decision(self, entrypoint, intent_kind):
        from keyrgb.tray import deck_pipeline

        tray = make_owner_backed_mock_tray(is_off=False)
        # Normal tray for off intents; for restore intents put it in the
        # corresponding off state so the decision is should_commit.
        if intent_kind is SleepWakeIntentKind.MANUAL_ON:
            tray.tray_idle_power_state.user_forced_off = True
            tray._user_forced_off = True
            tray.is_off = True
            tray.config.brightness = 25
        elif intent_kind is SleepWakeIntentKind.POWER_RESUME:
            tray.tray_idle_power_state.power_forced_off = True
            tray._power_forced_off = True
            tray.is_off = True
            tray.config.brightness = 25
            tray.config.effect = "none"
            # Avoid dim-temp branching.
            tray.tray_idle_power_state.dim_temp_active = False
        elif intent_kind is SleepWakeIntentKind.MANUAL_OFF:
            tray.tray_idle_power_state.user_forced_off = False
            tray.is_off = False
        elif intent_kind is SleepWakeIntentKind.POWER_OFF:
            tray.tray_idle_power_state.power_forced_off = False
            tray.is_off = False

        with patch.object(deck_pipeline, "decide_sleep_wake", wraps=deck_pipeline.decide_sleep_wake) as mock_decide:
            mod = __import__("keyrgb.tray.controllers.lighting_controller", fromlist=[entrypoint])
            fn = getattr(mod, entrypoint)
            # Power restore/turn_on need a start mock to avoid hardware writes.
            if entrypoint in ("power_restore", "turn_on"):
                with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", return_value=True):
                    fn(tray)
            else:
                fn(tray)

            # Exactly one pipeline decision for the public entrypoint.
            assert mock_decide.call_count == 1
            called_intent = mock_decide.call_args[0][1]
            assert called_intent.kind is intent_kind

    def test_injected_power_state_facades_still_call_pipeline(self):
        from keyrgb.tray import deck_pipeline
        from keyrgb.tray.controllers._power import _lighting_power_state as lps

        tray = make_owner_backed_mock_tray(is_off=False)
        with patch.object(deck_pipeline, "decide_sleep_wake", wraps=deck_pipeline.decide_sleep_wake) as mock_decide:
            lps.turn_off_impl(
                tray,
                try_log_event=MagicMock(),
                software_effect_target_routes_aux_devices=lambda _: False,
                turn_off_secondary_software_targets=lambda _: None,
            )
            assert mock_decide.call_count == 1
            assert mock_decide.call_args[0][1].kind is SleepWakeIntentKind.MANUAL_OFF


class TestBareIsOffNarrowOverride:
    def test_bare_is_off_turn_on_still_restores(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on
        from keyrgb.tray.deck_pipeline import hardware_apply_deferred

        tray = _bare_is_off_tray(last_brightness=20)
        tray.config.brightness = 0
        tray.config.effect = "none"

        assert hardware_apply_deferred(tray) is False
        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", return_value=True):
            turn_on(tray)

        assert tray.is_off is False
        assert hardware_apply_deferred(tray) is False

    def test_bare_is_off_power_restore_still_restores(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore
        from keyrgb.tray.deck_pipeline import hardware_apply_deferred

        tray = _bare_is_off_tray(last_brightness=42)
        tray.config.brightness = 25
        tray.config.effect = "none"

        assert hardware_apply_deferred(tray) is False
        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", return_value=True):
            power_restore(tray)

        assert tray.is_off is False
        assert tray.tray_idle_power_state.power_forced_off is False

    def test_config_scheduler_deferral_still_false_for_bare_is_off(self):
        from keyrgb.tray.deck_pipeline import hardware_apply_deferred

        tray = _bare_is_off_tray()
        # Bare is_off must not make scheduler/power-source think the deck is
        # off-family and defer hardware apply.
        assert hardware_apply_deferred(tray) is False
        # A true off-family state must defer.
        tray2 = make_owner_backed_mock_tray(is_off=True, user_forced_off=True)
        assert hardware_apply_deferred(tray2) is True


class TestRestoringFirewall:
    def test_state_is_restoring_during_start_callback(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on

        tray = _bare_is_off_tray(last_brightness=30)
        tray.config.brightness = 0
        tray.config.effect = "none"

        seen: list[DeckState] = []

        def fake_start(tray_arg, **_kwargs):
            seen.append(tray_arg.tray_idle_power_state.deck_state)
            return True

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", side_effect=fake_start):
            turn_on(tray)

        assert seen == [DeckState.RESTORING]
        # After the blocking fade the pipeline stores LIT (or DIM_TEMP).
        assert tray.tray_idle_power_state.deck_state in (DeckState.LIT, DeckState.DIM_TEMP)

    def test_state_is_restoring_during_power_restore_start(self):
        from keyrgb.tray.controllers.lighting_controller import power_restore

        tray = make_owner_backed_mock_tray(is_off=True, power_forced_off=True, last_brightness=25)
        tray.config.brightness = 25
        tray.config.effect = "none"

        seen: list[DeckState] = []

        def fake_start(tray_arg, **_kwargs):
            seen.append(tray_arg.tray_idle_power_state.deck_state)
            return True

        with patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", side_effect=fake_start):
            power_restore(tray)

        assert seen == [DeckState.RESTORING]

    def test_duplicate_wake_coalesces_while_restoring(self):
        from keyrgb.tray.deck_pipeline import _store_deck_state, commit_lighting_power_intent

        tray = make_owner_backed_mock_tray(is_off=True, power_forced_off=True, last_brightness=25)
        tray.config.brightness = 25
        _store_deck_state(tray, DeckState.RESTORING)

        second_calls: list[int] = []

        def second_leaf():
            second_calls.append(1)
            return True

        committed = commit_lighting_power_intent(tray, SleepWakeIntentKind.POWER_RESUME, second_leaf)

        assert committed is False
        assert second_calls == []

    def test_restore_failure_reverts_to_origin(self):
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent

        tray = _bare_is_off_tray(last_brightness=25)
        tray.config.brightness = 0
        origin = tray.tray_idle_power_state.deck_state
        assert origin is DeckState.LIT

        def failing_leaf():
            # Simulate a leaf that raises before clearing is_off.
            raise RuntimeError("synthetic failure")

        with pytest.raises(RuntimeError, match="synthetic failure"):
            commit_lighting_power_intent(tray, SleepWakeIntentKind.MANUAL_ON, failing_leaf)

        assert tray.tray_idle_power_state.deck_state is origin

    def test_reactive_manual_restore_seeds_once_and_consumes_only_original(self):
        from keyrgb.tray.controllers.lighting_controller import turn_on

        tray = _bare_is_off_tray(last_brightness=30)
        tray.config.brightness = 30
        tray.config.effect = "reactive_ripple"

        with (
            patch(
                "keyrgb.core.effects.reactive._reactive_restore_seed.seed_reactive_restore_windows",
                return_value=True,
            ) as seed,
            patch(
                "keyrgb.core.effects.reactive._reactive_restore_seed.apply_queued_reactive_restore_seed",
                return_value=False,
            ) as consume,
            patch("keyrgb.tray.controllers.lighting_controller.start_current_effect", return_value=True),
        ):
            turn_on(tray)

        seed.assert_called_once_with(
            tray.engine,
            fade_in_duration_s=pytest.approx(0.6),
        )
        consume.assert_called_once_with(tray.engine)

    def test_already_controller_sleep_dark_power_off_stays_immediate_no_fade(self):
        from keyrgb.tray.controllers.lighting_controller import power_turn_off

        tray = make_owner_backed_mock_tray(is_off=False)
        tray.tray_idle_power_state.controller_sleep_off = True
        tray.engine.turn_off = MagicMock()

        with (
            patch(
                "keyrgb.tray.controllers.software_target_controller.software_effect_target_routes_aux_devices",
                return_value=False,
            ),
            patch("keyrgb.tray.controllers.secondary_static_scene.turn_off_secondary_profile_areas"),
        ):
            power_turn_off(tray)

        tray.engine.turn_off.assert_called_once_with()
        assert tray.engine.turn_off.call_args.kwargs.get("fade") is not True


class TestExtractedPipelineCoverage:
    def test_store_deck_state_swallows_assignment_errors(self) -> None:
        from keyrgb.tray.deck_pipeline import _store_deck_state

        with patch(
            "keyrgb.tray._deck_state_store.ensure_tray_idle_power_state",
            side_effect=TypeError("synthetic"),
        ):
            _store_deck_state(object(), DeckState.LIT)

    def test_deferred_plan_does_not_run_leaf(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
        from keyrgb.tray.deck_state import SleepWakePlan

        tray = make_owner_backed_mock_tray(is_off=False)
        calls: list[int] = []

        with patch(
            "keyrgb.tray.deck_pipeline.decide_sleep_wake",
            return_value=SleepWakePlan(state=DeckState.LIT, should_commit=False, deferred=True),
        ):
            committed = commit_lighting_power_intent(
                tray,
                SleepWakeIntentKind.MANUAL_OFF,
                lambda: calls.append(1),
            )

        assert committed is False
        assert calls == []

    def test_restore_leaf_false_reverts_origin(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent

        tray = _bare_is_off_tray(last_brightness=25)
        tray.config.brightness = 25
        origin = tray.tray_idle_power_state.deck_state

        committed = commit_lighting_power_intent(tray, SleepWakeIntentKind.MANUAL_ON, lambda: False)

        assert committed is False
        assert tray.tray_idle_power_state.deck_state is origin

    def test_restore_leaf_keeps_is_off_as_failure(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent

        tray = _bare_is_off_tray(last_brightness=25)
        tray.config.brightness = 25

        def _leaf() -> bool:
            tray.is_off = True
            return True

        committed = commit_lighting_power_intent(tray, SleepWakeIntentKind.MANUAL_ON, _leaf)

        assert committed is False

    def test_reactive_seed_and_consume_errors_are_nonfatal(self) -> None:
        from keyrgb.tray._deck_lighting_power import (
            _consume_lighting_power_restore_seed,
            _seed_lighting_power_restore_windows,
        )

        tray = make_owner_backed_mock_tray(is_off=False)
        tray.config.effect = "reactive_ripple"

        with patch(
            "keyrgb.core.effects.reactive._reactive_restore_seed.seed_reactive_restore_windows",
            side_effect=TypeError("synthetic seed"),
        ):
            assert _seed_lighting_power_restore_windows(tray, fade_in_duration_s=0.1) is False

        with patch(
            "keyrgb.core.effects.reactive._reactive_restore_seed.apply_queued_reactive_restore_seed",
            side_effect=ValueError("synthetic consume"),
        ):
            _consume_lighting_power_restore_seed(tray)

    def test_keyboard_wake_uses_dim_temp_and_clears_resume_guard(self) -> None:
        from keyrgb.tray._deck_sleep_wake_commits import _commit_keyboard_wake

        tray = make_owner_backed_mock_tray(is_off=True, dim_temp_active=True, dim_temp_target_brightness=8)
        tray.tray_idle_power_state.controller_sleep_resume_guard = True

        with (
            patch(
                "keyrgb.tray.pollers.hardware._controller_sleep.restart_effect_after_firmware_wake_best_effort",
                return_value=True,
            ),
            patch("keyrgb.tray.pollers.hardware._recovery.controller_sleep_resume_guard_active", return_value=True),
            patch("keyrgb.tray.pollers.hardware._recovery.set_controller_sleep_resume_guard") as set_guard,
            patch("keyrgb.tray.pollers.hardware._recovery._seed_reactive_restore_damp_best_effort"),
            patch("keyrgb.tray.pollers.hardware._recovery.set_controller_sleep_off"),
            patch("keyrgb.tray.pollers.hardware._recovery._refresh_ui_without_icon_animation"),
        ):
            assert _commit_keyboard_wake(tray, now=1.0, dim_temp_target=None) is True

        set_guard.assert_called_once_with(tray, False)

    def test_unknown_idle_intent_is_a_noop(self) -> None:
        from keyrgb.tray._deck_sleep_wake_commits import _commit_idle_action

        tray = make_owner_backed_mock_tray(is_off=False)
        assert _commit_idle_action(tray, SleepWakeIntentKind.AUTO_HEAL, dim_temp_brightness=5) is False

    def test_derive_deck_state_falls_back_when_bool_reads_fail(self) -> None:
        from keyrgb.tray.deck_pipeline import derive_deck_state

        tray = make_owner_backed_mock_tray(is_off=False, user_forced_off=True)
        with patch(
            "keyrgb.tray.idle_power_state.read_idle_power_state_bool_field",
            side_effect=TypeError("synthetic"),
        ):
            assert derive_deck_state(tray) is DeckState.USER_OFF
