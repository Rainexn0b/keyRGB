# Reactive Typing — Smoothness Upgrades (Ripple + Fade)

> Date: 2026-07-31
> Status: implemented and validated locally
> Scope: `src/core/effects/reactive/` animation timing, input batching, pulse decay, ripple overlay cost
> Related: `reactive-typing-improvement-plan.md` (maintainability lane; orthogonal to this work)

---

## Background

A review of the reactive typing effects (`reactive_ripple`, `reactive_fade`) found four
smoothness/responsiveness issues, all confirmed in code:

1. **Fixed nominal dt** — the loops aged pulses by a hardcoded 1/60 s and *then* slept a
   full 1/60 s on top of render work. Real frame period was `dt + work` (typically
   20–30 ms with USB writes), so the effective frame rate was ~35–50 fps and jittery,
   animations ran slower than wall-clock, and the rainbow hue cycle speed wobbled with
   render load.
2. **One keypress per frame** — `poll_keypress_slot_id` drained each evdev batch but
   returned only the *first* mapped keydown; the rest were consumed and discarded.
   Fast typing produced fewer pulses than physical presses.
3. **Linear decay tails** — `intensity = 1 - age/ttl` visibly snaps off at the tail on
   8-bit LED hardware.
4. **Dead-ring scanning** — ripple pulses whose ring had fully left the matrix still
   scanned a `(2·⌈radius+band⌉+1)²` box every frame until TTL expiry (multiplied by
   every pulse in a typing burst).

## What landed

### 1. Real-dt frame timing (both loops)

- `utils.frame_elapsed_dt_s(...)` — ages pulses by the *measured* frame delta, clamped
  to `MAX_FRAME_DT_S = 0.25` so suspend/GC stalls fast-forward gracefully instead of
  teleporting the animation. First frame uses the nominal dt.
- `utils.remaining_frame_delay_s(...)` — the loop sleeps only `nominal_dt - work_time`,
  keeping the period near 60 fps regardless of evdev/USB cost.
- Ripple hue advance is now time-based: `_HUE_ADVANCE_DEG_PER_S = 120.0`
  (identical to the historical 2.0 deg/frame at 60 fps, but frame-rate independent).
  The AST guard test (`test_global_hue_formula_is_fixed_rate_not_pace_coupled`) still
  passes — the advance remains decoupled from `pace`.

### 2. One pulse per physical press

- `input.poll_keypress_slot_ids(devices) -> list[str]` collects **every** mapped
  keydown in a batch; the loops spawn a pulse per slot id.
- Tested facades preserved: `poll_keypress_slot_id` (singular) remains as a thin
  wrapper returning the first press, and `_PressSource.poll_slot_id` delegates to the
  new `_PressSource.poll_slot_ids`. Synthetic fallback still returns the `""` sentinel
  (now as `[""]`).

### 3. Ease-out decay

- `utils.pulse_decay_ease_out(age_s, ttl_s) = (1 - t)**1.5` replaces linear decay in both
  `build_fade_overlay_into` and `build_ripple_overlay_into`. Zero slope at end-of-life
  means the tail dissolves instead of snapping. TTL and peak brightness are unchanged.
  (Exponent 1.5 chosen over a full quadratic after hardware feedback: `(1-t)**2`
  read too dim mid-life on a real deck.)

### 3b. Wall-clock retune of pulse lifetimes (post-release hardware feedback)

The real-dt fix (item 1) exposed that the historical TTL constants were tuned against
frames that really ran ~1.6x slower than nominal — the designed speed had never
actually shipped. At true 60 fps the ripple crossed the full 25-key matrix in 0.65s
(~38 keys/s, "extremely fast and barely perceptible"). Constants retuned, no quality
cost (frame rate and smoothness are unchanged — the wavefront simply moves slower):

- Ripple: `_BASE_PULSE_TTL_S = 1.32s` (was 0.65s; 1.20s + 10% after second round
  of hardware feedback so the 50% speed-slider position reads as the middle)
- Fade: `_BASE_PULSE_TTL_S = 0.75s` (was 0.48s)

Both are still divided by `pace`, so the speed slider works as before.

**Pace range rescale (third round of hardware feedback):** the shared quadratic pace
mapping (`0.25 + 9.75·(s/10)²`) made slider 3 feel like the perceptual middle. Both
reactive loops now call `pace(engine, min_factor=0.25, max_factor=3.76)`, which lands
slider 5 on the old slider-3 pace (1.13x) and caps slider 10 at the old slider-6 pace
(3.76x). Scoped to the reactive loops (`_PACE_MIN_FACTOR`/`_PACE_MAX_FACTOR` module
constants) so the other software effects keep the shared mapping.

### 3c. Per-pulse radius normalization — the wave now visibly crosses the whole deck

Hardware feedback: the ripple appeared to "stop" around the far numpad corner.
Root cause: the ring always expanded to the *global* `max_radius` (25 keys) while
intensity decayed with age. An interior press covers the deck in the first ~50% of
the pulse's life; the wavefront then continued invisibly beyond the edges and was at
~9% brightness by the time it mathematically reached the far corner. Since the
wavefront is a Manhattan diamond, the last reachable point is always the farthest
*corner* — press-location dependent, matching the reported numpad-9/numpad-1 stops.

Fix in `build_ripple_overlay_into`:

- Each pulse's expansion is normalized to its **own farthest in-bounds key**
  (`max_d`). The ring spends its entire TTL travelling across the deck and arrives
  at the far corner exactly at end of life. Trade-off: wave speed is now
  location-dependent (corner press crosses 25 keys per TTL, center press ~13);
  in exchange every press produces a full-deck crossing in the same wall-clock time.
- Decay window stretched by `_DECAY_TTL_STRETCH = 1.2` so the far-edge "touchdown"
  lands at ~7% intensity instead of exactly zero.
- The earlier dead-ring skip is now obsolete (the radius can never outrun the deck)
  and was removed; interior pulses also scan smaller diamonds than before.

### 4. Ripple overlay cost reduction

- **Diamond iteration**: the scan iterates the Manhattan diamond `|dr|+|dc| <= radius_i`
  directly instead of scanning the bounding square and filtering — ~2× fewer cell
  visits, identical output (verified against a brute-force reference in tests).
- **Per-pulse radius cap** (see 3c): interior pulses scan diamonds bounded by their
  own farthest-key distance instead of the global 25-key radius, further shrinking
  the per-frame scan area during typing bursts.

## Files changed

- `src/core/effects/reactive/input.py` — plural poller + singular wrapper
- `src/core/effects/reactive/utils.py` — `poll_slot_ids`, timing helpers, ease-out
- `src/core/effects/reactive/_ripple_helpers.py` — ease-out intensity, dead-ring skip,
  diamond iteration
- `src/core/effects/reactive/_fade_loop.py` — real-dt loop, multi-press spawn
- `src/core/effects/reactive/_ripple_loop.py` — real-dt loop, multi-press spawn,
  per-second hue
- `src/core/effects/reactive/__init__.py` — export `poll_keypress_slot_ids`
- `tests/core/effects/reactive/core/test_reactive_smoothness_unit.py` — new (13 tests)
- `tests/core/effects/reactive/core/test_reactive_ripple_loop_unit.py` — mock updated
  to plural protocol + multi-press loop test
- `tests/core/effects/reactive/core/test_reactive_input_lifecycle_unit.py` — patch
  target updated to plural poller
- `tests/core/effects/rendering/test_effects_sw_visibility_unit.py` — fake press
  source updated to plural protocol

## Validation

- `.venv/bin/python -m pytest tests -q` — **3373 passed, 1 skipped**
- `.venv/bin/python -m buildpython --run-steps=19` — **PASS** (0 new broad-exception
  debt; the plural poller reuses the existing narrow exception sets)
- `ruff check` on all touched files — clean

## Frame-timing analysis from runtime log (2026-07-31, second pass)

User report: "every 3rd or 5th ripple press experiences a slight lag mid-propagation".
Analysis of `keyrgb-debug.log` (`--capture-runtime-log=full`) using the per-frame
`kb.set_key_colors (t=...)` timestamps:

- **Baseline frame period is ~45-49ms (~21fps), not 60fps.** A full ITE8291R3 frame
  costs 12 synchronous USB transfers (6 rows x row-index + row-data) plus 12 x 1ms
  pacing sleeps. Real-dt aging keeps animation *speed* correct, but the deck
  physically cannot update faster; ripple smoothness then depends on how the ring
  phase aligns with frame quantization — "some ripples smoother than others".
- **Periodic mid-prop spikes to ~60ms** (45ms frame + ~15ms) match the 2s hardware
  poller's two synchronous USB reads (`get_brightness`/`is_off`) under `kb_lock`.
- Rare 0.6-1.3s spikes = mode reinit / effect churn (out of scope).

Fixes landed:

1. **Hardware-poll deferral during pulse bursts** — `should_defer_poll_for_reactive_pulses`
   (`_decisions.py`): while `_reactive_active_pulse_mix > 0` (read lock-free), the
   poller retries on a 0.5s cadence instead of grabbing `kb_lock`, bounded by a 5s
   staleness cap so disconnect/off-state detection cannot starve during continuous
   typing (`REACTIVE_PULSE_POLL_DEFER_MAX_S` / `_RETRY_S`).
2. **Row-diff writes (ITE8291R3), default ON** — `set_key_colors` skips row
   transfers whose payload is identical to the previous frame. Hardware-validated
   2026-07-31 (no stale/blank rows across three captures); opt out with
   `KEYRGB_ITE8291R3_SKIP_UNCHANGED_ROWS=0`. Biggest win on fade (single-key
   pulses write 1 row instead of 6) and ripple edge frames (~18ms vs ~45ms);
   ripple mid-prop touches most rows so the median gain there is small.
   `set_color`/`test_pattern` invalidate the diff cache.
3. **Adaptive overrun diagnostic** — `log_frame_overrun_if_slow` now budgets against
   an EWMA of the backend's own recent frame work (a hitch = slow *relative to
   neighbours*), so it stays meaningful on ~45ms/frame hardware instead of flagging
   every frame.
4. **Pacing delay default lowered to 0.25 ms for ite8291r3_perkey** — validated via
   A/B runtime captures (1 ms -> 0.5 ms -> 0.25 ms): frame p50 47ms -> 36.9ms ->
   35.9ms, p90 spread tightens to 1.1ms at 0.25ms, no dropped-report artifacts.
   `ITE8291R3_DEFAULT_REPORT_DELAY_S` in backend.py; env overrides still honored
   (`KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS`, global `KEYRGB_HID_REPORT_DELAY_MS`).
   `hid_report_delay_s_from_env` gained an optional `default_s` parameter;
   the shared 1 ms default is unchanged for other backends.

Measured end state on the validation deck: ~21fps -> ~28fps reactive rendering
with mid-propagation stalls eliminated (poller deferral) and a tight frame
distribution. Remaining known levers (not pulled): the every-frame user-mode
reassert (~5-8ms/frame) and the 0 pacing setting (~3ms/frame more) — both need
more hardware evidence before changing.

## Lever comparison protocol + other-backends audit (2026-07-31, third pass)

**New diagnostic lever (generic):** `KEYRGB_PER_KEY_MODE_POLICY=init_once` overrides
any backend's declared per-key mode policy
(`src.core.backends.policies.per_key_mode.per_key_mode_policy`).
For ITE8291R3 this removes the every-frame user-mode reassert (~2-4ms/frame).
Failure mode when a device DOES need the reassert: deck freezes, reverts to a
hardware effect, or goes dark mid-animation. Unset = backend default.

**A/B/C comparison (same capture command, env vars prepended):**

| Run | Env | Expected p50 |
|-----|-----|--------------|
| A (current default) | — | ~36ms (~28fps) — already captured |
| B | `KEYRGB_PER_KEY_MODE_POLICY=init_once` | ~32-33ms (~31fps) |
| C | B + `KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS=0` | ~29-30ms (~34fps) |

Promotion criteria: no visual freeze/revert/dark frames across a full typing
session, and the frame-gap analysis shows the expected step down.

**Result (2026-07-31, self-describing captures):** B promoted to default. The
first B capture was load-contaminated (p50 42.5ms, no render failures in log);
a back-to-back A2/B2 pair with the new `device config:` startup log line gave a
clean comparison:

| | A2 (reassert) | B2 (init_once) |
|---|---|---|
| p50 | 38.0ms | 35.5ms |
| p90 | 41.0ms | 37.9ms |
| stability | — | full session visually normal |

The r3 backend default is now `keyrgb_per_key_mode_policy = "init_once"` (the
generic `KEYRGB_PER_KEY_MODE_POLICY` env override still wins; restore the old
behavior with `=reassert_every_frame` if any firmware regresses).

**Run C result (pacing=0):** p50 34.8ms vs 35.5ms at 0.25ms — only ~0.7-1ms at
the median, far less than the ~3ms arithmetic suggested (0.25ms is already at
the syscall floor). Deliberately NOT promoted: invisible benefit, and pacing=0
removes the bus quiet time that insures other r3 firmware revisions. The
0.25ms default stands; `KEYRGB_ITE8291R3_PERKEY_REPORT_DELAY_MS=0` remains
available as a documented experiment.

Final validated lever state for ite8291r3_perkey (2026-07-31): pacing 0.25ms,
row-diff on, init_once — ~35ms p50 reactive frames (~28fps), no
mid-propagation stalls.

**Other backends:**

- `ite8291_perkey` (non-r3): also declares `reassert_every_frame` — the same
  env lever applies. Its `set_key_colors` rewrites the full matrix every frame
  (no row diffing); a row-diff port would follow the r3 pattern but needs
  hardware evidence first. Pacing shares the global 1ms default
  (`KEYRGB_ITE8291_PERKEY_REPORT_DELAY_MS` honored via `sleep_after_hid_report`).
- `ite8910_perkey`: already `init_once`; paces via
  `KEYRGB_ITE8910_PERKEY_REPORT_DELAY_MS` (global 1ms default).
- All other backends (sysfs, zones, uniform, composite): no per-report pacing
  and no every-frame reassert — single-transfer or sysfs writes with a different
  (much cheaper) frame cost profile. No action needed.
- Guardrail kept: no other backend's defaults were changed — the 0.25ms pacing
  and row-diff defaults are scoped to `ite8291r3_perkey`, the only backend with
  hardware validation evidence.

## Backend compatibility review (2026-07-31)

All changed helpers are consumed only inside the reactive package; backends see the
same final write surface (`set_key_colors`, `set_color`, `set_brightness`) with
unchanged signatures and semantics.

- Per-key backends (ITE8291R3 USB): color-map path unchanged; frame-signature
  dedupe intact.
- Uniform RGB backends (sysfs-leds): uniform fallback consumes overlay max-weight;
  the ease-out only reshapes the decay envelope.
- Brightness-only sysfs backends: pulse-mix → hardware-lift path untouched; mix
  target still derives from overlay max weight.
- Synthetic/no-evdev fallback: `""` sentinel contract preserved and tested.

## Residual notes / follow-ups

- The 1.32s / 0.75s base TTLs, 1.5 decay exponent, 1.2 decay stretch, and 0.25..3.76
  pace range are calibrated against three rounds of hardware feedback on ITE8291R3;
  all are named module-level constants.
- The pulse-mix ramp (`PULSE_MIX_RISE_STEP` / `PULSE_MIX_DECAY_STEP` /
  `PULSE_MIX_INITIAL_RISE_STEP`) and `MAX_BRIGHTNESS_STEP_PER_FRAME` are still
  frame-coupled. With real-dt timing the frame rate is now a stable 60 fps, so these
  ramps are *more* consistent than before (they ran ~1.5x slower in wall-clock under
  the old jittery loop). Converting them to per-second rates would be the purist fix
  but would invalidate existing ramp-range tests for a ~50 ms tail difference —
  documented here as optional, not done.
- evdev events carry hardware timestamps; backdating `age_s` by
  `now - event.timestamp()` would remove the remaining frame-quantization of pulse
  phase. Deferred — small gain over the multi-press fix at 60 fps.
- Pulse object pooling (improvement-plan Item 6) remains unstarted; the per-pulse
  radius cap removes the bigger burst-typing cost first.
- Housekeeping observed (not touched, out of scope):
  `tests/core/effects/reactive/core/test_reactive_memory_buffers_unit.py.orig`
  looks like a merge/rebase leftover.
