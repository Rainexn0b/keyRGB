# Stale power ownership after suspend — 2026-10-05

## Host evidence

The running v0.37.0 AppImage's affected power-manager, event-policy, and lighting
state sources matched the repository before editing. No app restart, hardware
write, or forced suspend was used to collect evidence.

Local journal excerpts (CEST):

- 09:02:39: the battery profile transition persisted; the active profile file
  subsequently remained `Blue` (configured battery profile).
- 09:05:40–41: suspend/lid-close events logged `power:turn_off`.
- 09:18:28: both lid monitoring and source polling observed the lid open, but
  neither a restore log nor `power:restore` followed.
- 09:18:30: logind finished suspend and PowerDevil received
  `PrepareForSleep(false)`; KeyRGB still emitted no restore.
- 09:18:44/46: manual Off/On relit the keyboard, but the active profile stayed
  battery `Blue`, not the configured AC `Red`.
- During investigation, `/sys/class/power_supply/AC0/online` was `1`, UPower
  `OnBattery` was `false`, and the lid state was `open`. The process and its
  `dbus-monitor` child remained alive; no KeyRGB exception was logged.

Raw journals are local evidence under
`/tmp/opencode/keyrgb-resume-investigation/`; they are not committed. INFO logs
do not expose private generation/revision values, so the exact live thread
interleaving cannot be proven retrospectively. The following failure paths
are reproduced deterministically with the production coordinator and lighting
pipeline, and account for both observed symptoms.

## Root cause

1. Every accepted root transition advances the runtime revision, including a
   no-op power-source poll. A poll queued while a wake is deciding/waiting can
   invalidate that wake's revision before its restore callback runs.
2. `PowerEventPolicy` retains unexecuted restore intent, but only another wake
   event previously retried it. After the final lid-open/resume, there need not
   be another event. The remaining `power_forced_off` latch makes every source
   poll exit before AC/battery classification: a self-maintaining stale state.
3. Manual On cleared user/idle/native-sleep ownership but not power ownership.
   It could relight the deck while leaving `power_forced_off=True`. Source
   polling remained paused, and config/profile writes remained deferred.

This is explicit KeyRGB power ownership, not a new USB ID, permission problem,
or the controller's native ten-minute sleep timer.

## Fix and acceptance

- Retry retained, already-received wake intent inside the next serialized
  source iteration, after lid synchronization and before the power-off latch
  check. Do not repeat the original wake's stabilization delay.
- Preserve the original action flag, power-event generation, revision checks,
  and pipeline guard precedence. Polling alone must not wake a suspended deck;
  lid-close off policy, disabled actions/management, newer suspend, and manual
  Off must not be overridden. Docked/closed-lid operation remains valid when
  lid-close off is disabled.
- Manual On clears the legacy and typed power-off latch along with the other
  off owners, so normal power-source policy can run again.
- Consume the wake once; do not restart the effect on subsequent polls.

Regression coverage:
`tests/core/power/manager/test_power_manager_stale_wake_retry_unit.py`, including
the actual battery-to-AC stabilizer/classifier/policy with Blue → Red profiles.
Before the fix, both queued-wake cases and the manual Off/On case failed.

Validation uses focused power/tray tests, full hardware-disabled pytest,
targeted Ruff/format/mypy, and BuildPython steps 17 and 19. Live suspend testing
with a rebuilt/restarted application remains necessary; the original installed
AppImage is not hot-patched by these source edits.

## Files changed

- `keyrgb/core/power/management/manager.py`
- `keyrgb/core/power/policies/power_event_policy.py`
- `keyrgb/tray/controllers/_power/_lighting_power_state.py`
- `tests/core/power/manager/test_power_manager_stale_wake_retry_unit.py`
- `tests/core/power/policy/test_power_event_policy_unit.py`
- This investigation report.

## Primary-side validation ledger

Exact final commands and results:

```bash
# 749 passed
.venv/bin/python -m pytest tests/core/power tests/tray/controllers/power tests/tray/controllers/core/test_tray_lighting_controller_power_profile_unit.py tests/tray/pipeline tests/tray/test_lighting_power_pipeline_op2_unit.py tests/tray/pollers/idle_power tests/tray/pollers/hardware -q -o addopts=

# 5095 passed, 1 skipped (hardware tests disabled by the suite's default)
.venv/bin/python -m pytest -q -o addopts=

# All checks passed
.venv/bin/python -m ruff check keyrgb/core/power/management/manager.py keyrgb/core/power/policies/power_event_policy.py keyrgb/tray/controllers/_power/_lighting_power_state.py tests/core/power/manager/test_power_manager_stale_wake_retry_unit.py tests/core/power/policy/test_power_event_policy_unit.py

# 5 files already formatted
.venv/bin/python -m ruff format --check keyrgb/core/power/management/manager.py keyrgb/core/power/policies/power_event_policy.py keyrgb/tray/controllers/_power/_lighting_power_state.py tests/core/power/manager/test_power_manager_stale_wake_retry_unit.py tests/core/power/policy/test_power_event_policy_unit.py

# Success: no issues found in 3 source files
.venv/bin/python -m mypy keyrgb/core/power/management/manager.py keyrgb/core/power/policies/power_event_policy.py keyrgb/tray/controllers/_power/_lighting_power_state.py

# 2 selected steps passed; no architecture errors/warnings or unwaived broad catches
.venv/bin/python -m buildpython --run-steps=17,19

# Clean
git diff --check
```
