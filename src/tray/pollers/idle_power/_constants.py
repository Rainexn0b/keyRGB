from __future__ import annotations

# Idle-power policy timing constants.
# These control debounce windows and suppression periods for dim/undim
# and screen-dim-sync decisions.

# Seconds after an idle turn-off during which a "restore" action is
# suppressed.  Prevents rapid off/on flicker when the screen state
# fluctuates around the dim threshold shortly after keyboard lights
# were turned off.
POST_TURN_OFF_RESTORE_SUPPRESSION_S: float = 2.5

# Seconds after a system resume during which all idle-power actions are
# suppressed.  Avoids premature dimming or turn-off when the user has
# just woken the machine and input sensors have not yet caught up.
POST_RESUME_IDLE_ACTION_SUPPRESSION_S: float = 10.0
