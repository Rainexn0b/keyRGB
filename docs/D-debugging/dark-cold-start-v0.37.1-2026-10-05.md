# Dark keyboard after cold restart on v0.37.1 — 2026-10-05

## Status

Confirmed symptom: the built-in keyboard was dark from login; typing did not
relight it or produce reactive output. The screenshot's unchecked **Turn Off**
and **Software + Reactive Typing (Ripple)** describe application/menu state,
not verified physical light output.

The running package was v0.37.1. This is **a separate startup-mode failure from
the stale suspend/wake ownership defect fixed by that release**. The first
inspection found a synthetic mode-verification blind spot but lacked raw
controller state. The subsequent restart capture and user-authorized mode
reassert below confirmed inactive user mode as the immediate cause: one mode
command relit the existing rows at unchanged brightness. What originally put
the controller into that inactive state remains unknown.

During the first inspection the user closed the app and requested no relaunch;
no hardware query/write was performed then. The user subsequently restarted
and captured diagnostics themselves. With their explicit permission, the
follow-up queried status and sent one transient mode command under exclusive
ownership. No config/profile change, row rewrite, firmware save, app launch,
rebuild, installed-AppImage replacement, or suspend was performed by the
investigation. The user then authorized the narrowly scoped source fix below.

## Host evidence

- System boot: 12:10:41; desktop autostart: 12:11:10; tray ready: 12:11:11.
  The screenshot is at approximately 12:25. The user clarified that darkness
  began at login, not after ten minutes of inactivity.
- PID 1784 was the AppImage Python tray; PID 1817 was its AppImage runtime,
  not evidence of a second lighting writer. No OpenRGB/vendor RGB process
  appeared in the process scan.
- Installed metadata: `keyrgb-0.37.1.dist-info/METADATA`, `Version: 0.37.1`.
  The mounted power manager, power-event policy, and manual-On state sources
  matched the checkout's v0.37.1 implementation byte-for-byte. Startup,
  priming/start orchestration, hardware polling, and reactive rendering sources
  checked during investigation also matched.
- Backend/device: `048d:600b`, firmware descriptor `bcdDevice=0.03`;
  `ite8291r3_perkey`, `per_key_mode_policy=init_once`, unchanged-row skipping
  enabled, report delay 0.250 ms.
- The tray held `/dev/bus/usb/003/003` and `/dev/input/event3` open. The latter
  was the built-in `AT Translated Set 2 keyboard`. Both nodes had a user
  read/write ACL at inspection. This argues against ongoing USB/input access
  denial; it does not reconstruct every early-boot access attempt.
- `/sys/class/leds` contained only caps/num/scroll indicators, not a usable
  kernel keyboard-backlight interface. USB selection was appropriate here.
- Lid was open; AC was online. Current-boot journals contained initial
  `Lid state changed: None -> open`, but no suspend/lid-close cycle or
  `power:turn_off`/restore sequence. No USB reset/disconnect/error was found
  in the searched current-boot kernel messages.
- Saved intent: `autostart=true`, `effect=reactive_ripple`, brightness and
  per-key brightness 40, reactive brightness 50, red per-key colors,
  software target `keyboard`; native-controller sleep respect enabled.
  Screen-idle off and day/night policy were also enabled. Startup logged
  day brightness 40/50, not zero.
- The complete PID journal available at inspection contained startup INFO
  messages, no reported effect exception or subsequent brightness/off event,
  and clean power-monitor shutdown when the user quit at 12:31:33. Debug,
  brightness, and reactive-input logging were not enabled in that process.
- The saved config and active-profile timestamps did not change during this
  boot's inspection. No zero-brightness setting or black saved scene explains
  the symptom.

Thread wait-channel snapshots alone did not establish a deadlock. Read-only
`strace` attach was rejected by `kernel.yama.ptrace_scope=1`; noninteractive
sudo was unavailable. Private off-owner flags, effect generation, accepted
hardware observations, and startup control-report bytes were not captured.
The original process is now gone. Reopening would create a new observation,
not recover that process's state.

## Relation to v0.37.1

See [the suspend investigation](suspend-wake-stale-power-state-2026-10-05.md).
That release retries an already-received lid-open/resume restore invalidated
by a queued power-source revision, and clears stale power-off ownership on
manual On. These are suspend/lid recovery paths, not cold-start ITE mode
initialization. A fresh manager starts with no pending restore route.

`git diff v0.37.0 v0.37.1` showed no changes to the startup/prime/renderer paths
listed below. The fact that this occurred while running v0.37.1 establishes
an affected version, not that v0.37.1 introduced this symptom or that its
suspend fix failed on the same failure path.

## Demonstrated startup blind spot — candidate, not host diagnosis

This section records the **pre-fix first-pass** characterization. The initial
non-user-effect hypothesis was not the actual captured state: the follow-up
found effect `0x33` already present, but control `0x00` rather than active
control `0x02`. Both are missed by the same brightness/not-off-only prime.

1. `keyrgb/tray/app/_application_bindings.py:start_tray_runtime` starts the
   selected effect before config polling. Config startup deliberately avoids
   restarting an already-running matching loop effect.
2. `keyrgb/core/effects/engine_support/methods.py:prime_per_key_frame_method`
   requests mode reassertion for known explicit off or soft-on brightness 1;
   an ordinary fresh start at brightness 40 does not request it.
3. `keyrgb/core/effects/fades.py:prime_per_key_frame` writes rows and brightness,
   then checks `is_off()` and brightness. It can return success without sending
   a user-mode command when off is false and brightness is positive.
4. `keyrgb/core/backends/ite8291r3_perkey/device.py:is_off` checks control byte
   `0x01` only. It does not certify effect byte `0x33` (ITE user/per-key mode).
   A non-user hardware effect can therefore satisfy the prime's checks.
5. `keyrgb/core/effects/engine_support/start.py:_start_sw_effect` publishes the
   target as `_last_hw_mode_brightness` after a successful prime. Reactive
   `_render_runtime.py` with `init_once` then regards mode as initialized and
   sends subsequent rows without necessarily sending any mode command.

An in-memory probe used the production ITE protocol/device, production prime,
and production reactive renderer, with synthetic transport callbacks. It
never acquired hardware or instantiated the tray/config. Results at target 40:

| Synthetic initial state | Prime success | Final effect after changing reactive frame | Mode command sent |
|---|---|---|---|
| User mode `0x33`, not off, brightness 40 | Yes | `0x33` | No (expected) |
| Explicit off, brightness 0 | Yes | `0x33` | Yes (existing recovery works) |
| Hardware wave `0x03`, not off, brightness 40 | Yes | `0x03` | **No** |

This proves a mode-reclamation gap and can explain missing **software** reactive
output if the controller retains/reverts to a non-user mode. It does **not**
prove that the actual controller had effect `0x03`, that wave mode is dark,
or that a firmware cold-boot overwrite occurred. Other candidates include an
unobserved late EC/mode reset or unsuccessful initialization hidden by
best-effort/DEBUG-only priming paths. Ordinary native ten-minute sleep alone
does not fit the user's immediate-dark/no-keypress-wake account.

## Follow-up: restart capture and confirmed recovery

User-provided session:
`~/.cache/keyrgb/diagnostic-sessions/20261005T104336.313310Z/`.
Its header says `launcher=appimage`: `./keyrgb.sh --diagnostic-session` used
the installed AppImage, not the edited checkout. At follow-up inspection
there was one tray process and its AppImage runtime; only one process held
`keyrgb.lock`. The completed diagnostic capture was followed by another
ordinary AppImage launch, not concurrent tray ownership at inspection.

The 2,364-line capture shows:

- Startup rows at brightness 40 with `enable_user_mode=False` (line 287),
  brightness write 40 (288), `is_off=False` (289), readback 40 (290).
- 90 detected built-in keypresses and 632 `set_key_colors` calls, with reactive
  pulse activity and full visual scale. Input and the render worker were alive.
- Seven brightness/off observations, all 40/false; no zero read, explicit off,
  reported warning/error, or idle/suspend blanking in the capture.
- The source prime consequently skipped mode reassertion and published its
  initialized brightness cache; `init_once` frames retained that assumption.
  Brightness-proxy logs are not a complete raw-USB transcript, so command
  absence is inferred from this production path, not just a text count.

After the user quit, query-only capture acquired the same exclusive config
lock as the tray and the exact `048d:600b` USB interface. It sent only
`GET_EFFECT` (`8800000000000000`), without a lighting mutation:

```text
Dark response:        88 00 33 f0 28 00 00 00
                      control=0, effect=0x33, speed=0xf0, brightness=40
```

The user then authorized exactly one transient user-mode reassert at 40,
without changing colors, config, profiles, or saved firmware settings:

```text
Before:               88 00 33 f0 28 00 00 00
Single mode command:  08 02 33 00 28 00 00 00
After:                88 02 33 00 28 00 00 00
User observation:     "Yes, deck is lit"
```

Exact one-off commands, each separately authorized and run with the tray
closed (these are hardware operations, not automated validation):

```bash
PYTHONPATH="$PWD" .venv/bin/python /tmp/opencode/keyrgb-dark-after-restart-2026-10-05/query_ite_mode.py
PYTHONPATH="$PWD" .venv/bin/python /tmp/opencode/keyrgb-dark-after-restart-2026-10-05/reassert_ite_mode_once.py
```

This isolates the immediate missing activation: a mode command alone made the
previously written rows visible. It does not establish the original EC/boot
trigger or attribute it to the v0.37.1 suspend changes.

## Implemented prevention

- `keyrgb/core/backends/ite8291r3_perkey/device.py`: add optional
  `is_user_mode()` status verification for active control `0x02` and user
  effect `0x33`, including complete-response validation and raw DEBUG logging.
  Preserve existing `is_off()` semantics and native-sleep classification.
- `keyrgb/core/effects/fades.py`: use that optional probe in the existing
  locked hidden-row prime. Reassert once with `save=False` only when needed,
  after rows/brightness land, and verify the result before returning success.
  Healthy active mode and backends without the probe retain their previous
  startup behavior. Log reassertion, failure, and recoverable prime errors.
- `tests/core/effects/rendering/test_perkey_startup_mode_unit.py`: cover the
  exact captured inactive response, logging proxy delegation, active-mode
  no-reassert, non-user mode, ignored commands, malformed responses, native
  sleep/off semantics, recoverable/unexpected probe failures, and the actual
  engine's pre-worker prime/baseline publication.
- `CHANGELOG.md`: record this separate unreleased fix without changing the
  v0.37.1 release notes or unrelated packaging changes.

The new tests initially reproduced the captured-state failure (no mode report
despite prime success). Before implementation: 14 failed, 1 passed. The
subsequent engine integration test needed explicit in-memory device injection
because pytest correctly blocks production hardware acquisition; it now uses
that safe injection, not a hardware opt-in.

## First-pass validation and local evidence

These historical checks were run by the primary investigation, hardware-free,
before the fix. The synthetic probe asserts the old behavior and is not a
passing acceptance command for the corrected checkout:

```bash
# 59 passed
.venv/bin/python -m pytest tests/core/power/manager/test_power_manager_stale_wake_retry_unit.py tests/core/power/policy/test_power_event_policy_unit.py tests/core/effects/engine/test_effects_engine_start_soft_on_unit.py tests/core/effects/rendering/test_effects_perkey_brightness_args_unit.py tests/core/effects/reactive/rendering/test_reactive_render_brightness_policy_unit.py -q -o addopts=

# 215 passed
.venv/bin/python -m pytest tests/tray/app/test_tray_lifecycle_unit.py tests/tray/app/test_tray_startup_unit.py tests/tray/app/test_tray_startup_bootstrap_unit.py tests/tray/pollers/config/apply/test_tray_config_apply_lifecycle_integration_unit.py tests/tray/pollers/hardware tests/core/backends/ite/test_ite8291r3_native_backend_unit.py -q -o addopts=

# PASS: non-user/nonzero startup mode not reclaimed by prime/reactive frame
PYTHONPATH="$PWD" .venv/bin/python /tmp/opencode/keyrgb-dark-after-restart-2026-10-05/probe_startup_mode.py

# No startup/renderer changes between these releases
git diff v0.37.0 v0.37.1 -- keyrgb/core/effects/fades.py keyrgb/core/effects/engine_support/start.py keyrgb/core/effects/engine_support/methods.py keyrgb/core/effects/reactive/_render_runtime.py keyrgb/tray/app/_application_bindings.py keyrgb/tray/app/lifecycle.py keyrgb/tray/pollers/hardware/_polled_state.py

# No whitespace diagnostics. First exits 0; no-index exits 1 for added-file difference.
git diff --check
git diff --no-index --check /dev/null docs/D-debugging/dark-cold-start-v0.37.1-2026-10-05.md
```

Startup journal and the synthetic characterization script are local artifacts
under `/tmp/opencode/keyrgb-dark-after-restart-2026-10-05/`, not committed.
Those passing first-pass tests did not prove live cold-start recovery: their
positive brightness/off checks did not establish the real active mode.

## Fix validation

Exact primary-side commands:

```bash
# 62 passed
.venv/bin/python -m pytest tests/core/effects/rendering/test_perkey_startup_mode_unit.py tests/core/effects/rendering/test_effects_perkey_brightness_args_unit.py tests/core/effects/engine/test_effects_engine_start_soft_on_unit.py tests/core/backends/ite/test_ite8291r3_native_backend_unit.py -q -o addopts=

# All checks passed; 3 files already formatted
.venv/bin/python -m ruff check keyrgb/core/backends/ite8291r3_perkey/device.py keyrgb/core/effects/fades.py tests/core/effects/rendering/test_perkey_startup_mode_unit.py
.venv/bin/python -m ruff format --check keyrgb/core/backends/ite8291r3_perkey/device.py keyrgb/core/effects/fades.py tests/core/effects/rendering/test_perkey_startup_mode_unit.py

# Success: no issues found in 2 source files
.venv/bin/python -m mypy keyrgb/core/backends/ite8291r3_perkey/device.py keyrgb/core/effects/fades.py

# 2 steps passed; 0 architecture errors/warnings, 0 unwaived broad-catch debt
.venv/bin/python -m buildpython --run-steps=17,19

# Final merged full suite: 5171 passed, 1 skipped (hardware disabled)
.venv/bin/python -m pytest -q -o addopts=

# No whitespace diagnostics; added-file no-index checks exit 1 for differences
git diff --check
git diff --no-index --check /dev/null tests/core/effects/rendering/test_perkey_startup_mode_unit.py
git diff --no-index --check /dev/null docs/D-debugging/dark-cold-start-v0.37.1-2026-10-05.md
```

The first post-fix full run, before adding the engine integration case, passed
5,170 tests with 1 skip. The query/reassert scripts are local artifacts under
the same `/tmp/opencode/keyrgb-dark-after-restart-2026-10-05/` directory. They
are **not** general support commands: the reassert script deliberately performs
a user-authorized lighting mutation, and both assume this exact device/lock.

## Remaining acceptance and risk

- Capture the **next cold boot's initial** control/effect/brightness, the
  post-prime response, mode commands, first successful frame, input evidence,
  and power/sleep owners before manually relaunching. A diagnostic session
  launched only after login may heal and miss the original failure.
- The corrected checkout has not been launched on hardware, packaged, or
  installed. The current v0.37.1 AppImage still contains the old startup prime.
  Validate a rebuilt/source-runtime cold start before claiming deployment.
- This is a bounded startup fix, not a new background mode watcher. A later
  EC/mode loss after an already-successful prime is separate remaining risk.
- Do not globally enable per-frame reassertion, weaken forced-off/native-sleep
  precedence, add USB IDs, change udev access, or blame the suspend fix.
