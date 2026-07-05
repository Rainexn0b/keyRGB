# KDE Brightness / Idle-Dim Bug Handoff

Date: 2026-06-08

## Summary

Two bugs remain unresolved on KDE Plasma / Wayland:

1. Manually changing screen brightness can still turn the keyboard lighting off.
2. The keyboard does not reliably wake from touchpad activity; it usually wakes only after a keyboard keypress.

The latest run confirms that the current "sync to KDE dim timeout and use input idle" strategy is still not robust enough on this machine.

The user plans to reset back to `main` and continue from a clean codebase. This document is intended to preserve the findings from the final debug run and the investigation paths already tried.

## User expectation

Desired behavior:

- Keyboard dim/off must follow screen dim events only.
- Manual screen brightness changes must never affect keyboard lighting.
- Touchpad and other normal desktop interaction should wake the keyboard, not just keypresses.

## Environment from latest log

From `keyrgb-idle-dim-debug.log`:

- Desktop: KDE Plasma / Wayland
- Distro: CachyOS
- Kernel: `7.0.10-1-cachyos`
- KeyRGB version in log: `0.25.11`
- Backend: `ite8291r3`
- Device: `0x048d:0x600b`
- Power state during run: AC online
- Config brightness: `40`
- Dim timeout sourced by current experiment: `desktop_idle_timeout_s=10.0`

## Final log findings

### 1. The new KDE timeout path was active

The latest log includes:

- `desktop_idle_timeout_s=10.0`
- `desktop_session_idle_s=None`

That proves the run was using the newer KDE-timeout-based path, not the older backlight-classification path.

### 2. Desktop session idle lookup never succeeded

Across the latest log, every snapshot showed:

- `desktop_session_idle_s=None`

That means the new "prefer desktop session idle first" code path did not successfully read idle time from KDE on the user system. The implementation therefore fell back to local evdev idle tracking.

### 3. Local input idle continued to advance through brightness interaction

Before the first unwanted shutoff:

- `local_input_idle_s` climbed steadily from `0.0` to `9.9`
- then hit `10.5`
- immediately after that, KeyRGB emitted:
  - `EVENT idle_power:turn_off`
  - `dimmed=True`
  - `session_idle=True`

This means the app believed there had been no qualifying local activity for roughly the full KDE dim timeout.

### 4. Manual brightness interaction happened while KeyRGB still thought the session was idle

After the first turn-off, the log shows:

- `EVENT hardware:brightness_change ... new=8 old=40 raw=8`

But idle state did not reset at that point:

- `desktop_session_idle_s=None`
- `local_input_idle_s` continued increasing
- `dimmed=True`
- `session_idle=True`

This is the clearest evidence that manual brightness interaction itself was not being counted as activity by the current detection path.

### 5. Restore happened only when input detection finally reset to zero

Later the log shows:

- `computed_action=restore`
- `local_input_idle_s=0.0`
- `session_idle=False`

This indicates restore still depends on the observed input source resetting, and that reset only happened after an input event that the current detector actually recognized. In user testing, this matched keyboard keypress, not touchpad movement.

### 6. The second unwanted turn-off reproduced the same pattern

A second full cycle appears later in the same log:

- `local_input_idle_s` again rises to around `10.3`
- `computed_action=turn_off`
- `hardware:off_state_change new=True old=False`

This confirms the issue is repeatable and not a one-off transition artifact.

## Likely root cause

The current strategy still depends on an activity source that is incomplete on this system.

More specifically:

- KDE timeout reading works: `desktop_idle_timeout_s=10.0`
- KDE desktop session idle reading does not work: `desktop_session_idle_s=None`
- fallback local evdev input tracking is incomplete for the user's real interaction path

As a result:

- touchpad-driven brightness changes can look like "10 seconds of inactivity"
- touchpad movement may fail to wake the keyboard

## What was tried during this session

### Strategy A: backlight drop + logind + KDE brightness classification

Approach:

- detect dim from `/sys/class/backlight`
- debounce dim/undim transitions
- use `logind` idle as a sanity check
- add KDE D-Bus brightness monitoring to distinguish auto-dim from manual brightness changes

Observed failures:

- KDE dim occurred while `logind` still reported active / `idle_seconds=0.0`
- KDE D-Bus monitors started, but useful dim context was not reliably seen in the debug logs
- this did not solve the manual-brightness bug

### Strategy B: local evdev input fallback layered on top of backlight dim

Approach:

- keep brightness/backlight dim detection
- allow dim only if no recent local evdev activity

Observed failures:

- still vulnerable because brightness change and dim remained coupled
- still not robust against the user's actual touchpad interaction path

### Strategy C: ignore brightness as trigger and sync to KDE timeout

Approach:

- stop using brightness change as primary trigger on KDE
- read `DimDisplayIdleTimeoutSec` from `~/.config/powerdevilrc`
- compute idle from local evdev input

Observed failures:

- timeout value read correctly
- touchpad/brightness interactions still not reliably counted as activity
- bug persisted
- touchpad wake remained broken

### Strategy D: prefer desktop session idle before evdev fallback

Approach:

- read KDE/session idle via `qdbus6` / `gdbus` calls to `org.freedesktop.ScreenSaver.GetSessionIdleTime`
- use that first
- fall back to evdev only if desktop session idle is unavailable

Observed failure in final log:

- `desktop_session_idle_s` stayed `None` for the entire run
- the code never got a usable desktop/session idle signal on the user's machine

## Important conclusion

The bug is no longer primarily about "brightness detection." It is now about "activity detection."

The current code still turns off the keyboard because it believes the user has been idle for the KDE timeout. That belief is wrong during touchpad-driven brightness interaction and wrong during touchpad-only wake.

## Most likely next investigation paths

### Option 1: find a KDE-native idle source that actually works on this machine

This is the most promising direction.

Goal:

- query KDE or the session compositor for authoritative user-idle time
- ensure touchpad, mouse, brightness slider interaction, and normal pointer motion reset idle consistently

Candidates worth investigating on a clean tree:

- `org.freedesktop.ScreenSaver` on the real session bus, but verified live outside sandbox constraints
- KWin-specific D-Bus APIs, if any expose idle time or input activity directly
- Plasma/PowerDevil session services for current idle state or dim scheduling

Why this is promising:

- if a working desktop idle source exists, manual brightness changes will naturally count as activity
- touchpad wake should also work automatically

### Option 2: improve evdev input coverage if KDE idle remains unavailable

If no reliable KDE idle API can be used, revisit evdev, but assume the current implementation is missing real devices/events.

Specific things to verify on the user machine:

- which `/dev/input/event*` devices are visible to the running KeyRGB process
- whether the touchpad node is actually accessible from the app context
- whether touchpad motion events are emitted on the monitored device during slider use
- whether the device list changes across launch contexts, packaging, or permissions

Important note:

During sandboxed inspection in this session, only `/dev/input/event3` was visible to the Python process, which was the keyboard. That may be a sandbox artifact for this investigation environment, but if something similar happens in the real app runtime, it would explain both remaining bugs immediately.

### Option 3: abandon timeout-sync and return to explicit desktop dim-state integration

This is less attractive, but still possible if a reliable "screen is dimmed by idle policy" signal can be found.

That would require:

- a real KDE/PowerDevil dim-state signal
- not a generic brightness change signal
- not a heuristic derived from backlight level

Without that explicit signal, this route is likely to regress into the same brightness/manual-classification problem.

## Recommended next-agent plan

1. Reset to `main`.
2. Reproduce with a clean tree and a fresh debug log.
3. Before changing behavior, verify whether a live KDE/session idle API can be queried successfully outside the current sandbox constraints.
4. If that API exists and updates with touchpad/slider interaction, build the design around it.
5. Only if KDE idle cannot be made to work, inspect real evdev visibility and permissions for the running KeyRGB process.
6. Do not continue layering more brightness heuristics on top of the current implementation.

## Concrete evidence snippets from final log

### Timeout path active

- snapshots include `desktop_idle_timeout_s=10.0`

### Session idle source unavailable

- snapshots include `desktop_session_idle_s=None` throughout

### First bad turn-off

- `local_input_idle_s=9.9` while still `dimmed=False`
- next snapshot: `local_input_idle_s=10.5`, `computed_action=turn_off`, `session_idle=True`

### Brightness interaction did not reset activity

- `hardware:brightness_change ... new=8 old=40 raw=8`
- surrounding snapshots still show `desktop_session_idle_s=None`
- surrounding snapshots still show `local_input_idle_s` increasing through `12.6`, `13.1`, `13.6`, etc.

### Restore only after recognized activity

- `computed_action=restore`
- same snapshot shows `local_input_idle_s=0.0` and `session_idle=False`

### Second bad turn-off

- later cycle repeats with `local_input_idle_s=10.3`, `computed_action=turn_off`

## Files touched during the unsuccessful experiment

These are the main files involved in the attempt, in case the next agent wants context before discarding or selectively reusing anything:

- `src/tray/pollers/idle_power/polling.py`
- `src/tray/pollers/idle_power/_runtime.py`
- `src/tray/pollers/idle_power/local_input.py`
- `src/tray/pollers/idle_power/desktop_idle_timeout.py`
- `src/tray/pollers/idle_power/desktop_session_idle.py`
- `src/tray/pollers/idle_power/kde_brightness.py`
- `tests/tray/pollers/idle_power/runtime/*`

## Bottom line

Current status after the last log:

- brightness-trigger bug: still present
- touchpad wake bug: still present
- strongest current hypothesis: missing or unavailable desktop activity signal, with incomplete evdev fallback

The best next move is a clean-tree investigation centered on authoritative KDE idle/activity state, not further brightness heuristics.