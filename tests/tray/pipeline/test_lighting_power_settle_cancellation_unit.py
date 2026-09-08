from __future__ import annotations

from unittest.mock import patch

from keyrgb.tray.deck_state import DeckState, SleepWakeIntentKind
from tests.tray.fakes import make_owner_backed_mock_tray


class TestPendingSettleCancellation:
    def _settle_armed_tray(self, **overrides):
        from keyrgb.tray.pollers.hardware._controller_sleep import arm_controller_wake_settle

        tray = make_owner_backed_mock_tray(is_off=True, **overrides)
        tray.engine.kb.keyrgb_controller_wake_settle_s = 2.0
        assert arm_controller_wake_settle(tray, now=100.0) is True
        return tray

    def test_manual_off_noop_cancels_pending_settle(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
        from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_pending

        tray = self._settle_armed_tray(user_forced_off=True)
        tray._user_forced_off = True
        leaf_calls: list[int] = []

        committed = commit_lighting_power_intent(
            tray,
            SleepWakeIntentKind.MANUAL_OFF,
            lambda: leaf_calls.append(1),
        )

        assert committed is False
        assert leaf_calls == []
        assert controller_wake_settle_pending(tray) is False

    def test_blocked_power_resume_still_cancels_pending_settle(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
        from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_pending

        tray = self._settle_armed_tray(user_forced_off=True)
        tray._user_forced_off = True
        leaf_calls: list[int] = []

        committed = commit_lighting_power_intent(
            tray,
            SleepWakeIntentKind.POWER_RESUME,
            lambda: leaf_calls.append(1),
        )

        assert committed is False
        # Blocked-restore housekeeping still runs, with no stale deadline left.
        assert leaf_calls == [1]
        assert controller_wake_settle_pending(tray) is False

    def test_power_off_commit_cancels_pending_settle(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
        from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_pending

        tray = self._settle_armed_tray()
        leaf_calls: list[int] = []

        committed = commit_lighting_power_intent(
            tray,
            SleepWakeIntentKind.POWER_OFF,
            lambda: leaf_calls.append(1),
        )

        assert committed is True
        assert leaf_calls == [1]
        assert controller_wake_settle_pending(tray) is False
        assert tray.tray_idle_power_state.deck_state is DeckState.POWER_OFF

    def test_manual_on_deferred_plan_cancels_pending_settle(self) -> None:
        from keyrgb.tray.deck_pipeline import commit_lighting_power_intent
        from keyrgb.tray.deck_state import SleepWakePlan
        from keyrgb.tray.pollers.hardware._controller_sleep import controller_wake_settle_pending

        tray = self._settle_armed_tray()
        leaf_calls: list[int] = []

        with patch(
            "keyrgb.tray.deck_pipeline.decide_sleep_wake",
            return_value=SleepWakePlan(state=DeckState.LIT, should_commit=False, deferred=True),
        ):
            committed = commit_lighting_power_intent(
                tray,
                SleepWakeIntentKind.MANUAL_ON,
                lambda: leaf_calls.append(1),
            )

        assert committed is False
        assert leaf_calls == []
        assert controller_wake_settle_pending(tray) is False
