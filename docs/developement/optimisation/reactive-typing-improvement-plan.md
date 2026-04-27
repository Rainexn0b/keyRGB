# Reactive Typing — Improvement Plan

> Generated: 2026-04-27  
> Based on: full code-review of reactive effects, brightness management, power integration, GUI, config, and tests  
> See also: `docs/developement/bug-ongoing/reactive-typing/reactive-typing-flicker-postmortem-2026-04.md`

---

## Overview

The reactive typing system handles a genuinely difficult problem well. The pulse math, animation
smoothing, and per-key vs. uniform backend split are all correct. The weakest areas are:

1. Scattered engine state (13+ `_reactive_*` attributes with no owning struct)
2. A dense multi-condition hardware-lift gate that is hard to audit
3. Dual restore-phase timers that can de-sync
4. GUI dispatcher boilerplate (~400 lines of near-identical wiring)
5. Missing wake-path integration test (repeated regression site)

The items below are ordered by **ROI** (value / effort). None of them change user-facing
behaviour; all are pure maintainability and reliability improvements.

## Status Update

Status as of 2026-04-27:

- Items 1 through 5 are implemented and validated.
- Item 6 remains optional and has not been started.

The landed shape is slightly narrower and better than the original draft in one important
way: reactive compatibility writes are now explicit instead of hidden inside generic state
helpers.

Implemented outcome:

- `EffectsEngine` owns one mounted `_reactive_state = ReactiveRenderState(...)` field in
    init and stop.
- `ReactiveRestorePhase` replaces the old pending-bool plus timestamp pairing.
- The generic mirror from `set_engine_attr(...)` back onto top-level engine attrs is removed.
- Compatibility writes remain only where they are part of an existing tested contract:
    `_set_reactive_active_pulse_mix(...)` keeps its explicit cache-write/log path, and
    `clear_transition_state(...)` keeps an explicit compatibility-only clear path.
- Wake-path regression coverage landed in the existing reactive pulse brightness test slice.

Why this is preferable:

- mounted state is now the single default source of truth for reactive render state
- compatibility behavior is visible at the exact callsite that needs it
- logging-sensitive legacy behavior stays preserved without keeping a hidden global bridge
- future cleanup is safer because new reactive fields will not silently leak onto the engine

---

## Item 1 — Consolidate reactive render state into a dataclass

**Files affected:**
- `src/core/effects/reactive/_render_brightness_support.py`
- `src/core/effects/reactive/render.py`
- `src/core/effects/reactive/effects.py`
- `src/core/effects/reactive/_render_brightness.py`

**Problem:**  
13+ `_reactive_*` fields are scattered directly on the `EffectsEngine` object:

```
_reactive_active_pulse_mix
_reactive_disable_pulse_hw_lift_until
_reactive_post_restore_visual_damp_until
_reactive_post_restore_visual_damp_pending
_reactive_uniform_hw_streak
_reactive_*_debug_*   (several)
```

There is no single place to see "what is the reactive render state right now". Lifecycle
(init, reset-on-stop, reset-on-wake, reset-on-dim) must be chased across several modules.
Defensive `attrgetter()` + `try/except AttributeError` on every frame signals the fields are
not guaranteed to be present, which is a design smell.

**Target design:**

```python
@dataclass
class ReactiveRenderState:
    active_pulse_mix: float = 0.0
    uniform_hw_streak: int = 0
    disable_pulse_hw_lift_until: float = 0.0
    post_restore_visual_damp_until: float = 0.0
    post_restore_visual_damp_pending: bool = False
    last_rendered_brightness: int = 0
    # debug fields (zero-cost when KEYRGB_DEBUG_BRIGHTNESS is off)
    debug_last_logged: tuple | None = None
```

The engine owns one `_reactive_state: ReactiveRenderState` field, initialised in
`__init__`. All render/brightness helpers read from and write to this object. The
`attrgetter`/`try-except` pattern is replaced with direct attribute access.

**Acceptance criteria:**
- All existing reactive-brightness tests pass unchanged
- `_render_brightness_support.py::read_engine_attr` is no longer needed for reactive fields
- `grep "_reactive_" src/core/effects/` returns only the dataclass definition and its single
  mount point on the engine

**Effort estimate:** Medium (2–3 h, mostly mechanical rename + test pass)

---

## Item 2 — Extract the hardware-lift gate into a named predicate

**Files affected:**
- `src/core/effects/reactive/_render_brightness.py`

**Problem:**  
The 5-condition gate is evaluated inline with implicit short-circuit priority:

```python
allow_pulse_hw_lift = (
    not per_key_hw
    and uniform_hw_streak_count >= 6
    and pulse_mix > 0.0
    and eff > hw
    and not cooldown_active
)
```

The ordering matters: `per_key_hw` short-circuits first so the streak counter is never read
on per-key backends. This invariant is not documented. If the streak threshold changes
(6 → 4 for snappier response on slower hardware), it's not obvious which conditions must be
re-validated together.

**Target design:**

```python
def _can_lift_hw_brightness(
    *,
    per_key_hw: bool,
    uniform_hw_streak: int,
    pulse_mix: float,
    effective_brightness: int,
    current_hw_brightness: int,
    cooldown_active: bool,
) -> bool:
    """True when a uniform-only backend is allowed to temporarily raise hardware
    brightness to keep reactive pulses visible.

    Per-key backends never lift: pulse visibility is managed through per-key colour
    contrast, not hardware brightness.  The 6-frame streak gate prevents a single
    keypress from causing a brightness spike before the render loop is stable.
    """
    if per_key_hw:
        return False   # per-key: contrast path, never lift
    if uniform_hw_streak < 6:
        return False   # not enough stable frames yet
    return (
        pulse_mix > 0.0
        and effective_brightness > current_hw_brightness
        and not cooldown_active
    )
```

**Acceptance criteria:**
- Inline gate is fully replaced by `_can_lift_hw_brightness(...)` call
- Existing `test_reactive_pulse_brightness_unit.py` streak-gate tests pass
- Docstring documents the per-key short-circuit and the 6-frame rationale

**Effort estimate:** Low (< 1 h)

---

## Item 3 — Replace dual restore-phase timers with an enum state

**Files affected:**
- `src/core/effects/reactive/effects.py`
- `src/core/effects/reactive/render.py`
- `src/core/effects/reactive/_render_brightness_support.py` (if Item 1 done, via `ReactiveRenderState`)

**Problem:**  
Post-restore behaviour is tracked by two co-dependent fields:

```
_reactive_post_restore_visual_damp_until   (float, epoch timestamp)
_reactive_post_restore_visual_damp_pending (bool)
```

The `pending` flag means "damp the first post-restore pulse even if the timer has not been
set yet". Both fields must be set together and both must be cleared together. If a restore
path omits one, the damp silently fails or fires unexpectedly. The conditional in `render.py`
must check both:

```python
if pending:
    # seed the timer on the first post-restore keypress
    ...
elif now < damp_until:
    # apply damp
    ...
```

**Target design:**

```python
class _RestorePhase(Enum):
    NORMAL = "normal"
    DAMP_PENDING = "damp_pending"   # first post-restore keystroke not seen yet
    DAMPING = "damping"             # timer active, apply damp scale

@dataclass
class ReactiveRenderState:
    ...
    restore_phase: _RestorePhase = _RestorePhase.NORMAL
    restore_damp_until: float = 0.0
```

Transitions:
- `NORMAL → DAMP_PENDING`: on any restore (wake, manual profile change)
- `DAMP_PENDING → DAMPING`: on first keystroke after restore (seed `restore_damp_until`)
- `DAMPING → NORMAL`: when `now >= restore_damp_until`

**Acceptance criteria:**
- `_reactive_post_restore_visual_damp_pending` and `_reactive_post_restore_visual_damp_until`
  are removed
- Restore-damp tests in `test_reactive_pulse_brightness_unit.py` pass unchanged
- Each state transition has exactly one call site

**Effort estimate:** Medium (2 h; best done after Item 1 so it slots into the dataclass)

---

## Item 4 — Replace GUI dispatcher boilerplate with a higher-order wrapper

**Files affected:**
- `src/gui/windows/_reactive_color_wiring.py`

**Problem:**  
~400 lines contain 10+ `dispatch_*_change()` functions with identical structure:

```python
def dispatch_brightness_change(self) -> None:
    try:
        value = self._read_brightness_slider()
        self._adapter.commit_brightness(value)
    except _WRAP_SYNC_ERRORS as exc:
        _log_sync_error("brightness", exc)

def dispatch_trail_change(self) -> None:
    try:
        value = self._read_trail_slider()
        self._adapter.commit_trail(value)
    except _WRAP_SYNC_ERRORS as exc:
        _log_sync_error("trail", exc)
# ... 8 more identical structures
```

**Target design:**

```python
def _make_sync_dispatcher(name: str, read_fn: Callable, commit_fn: Callable) -> Callable:
    def _dispatch(self) -> None:
        try:
            commit_fn(self, read_fn(self))
        except _WRAP_SYNC_ERRORS as exc:
            _log_sync_error(name, exc)
    _dispatch.__name__ = f"dispatch_{name}_change"
    return _dispatch
```

Each dispatcher becomes a one-liner declaration:

```python
dispatch_brightness_change = _make_sync_dispatcher(
    "brightness", ReactiveColorWiring._read_brightness_slider,
    ReactiveColorWiring._commit_brightness,
)
```

**Acceptance criteria:**
- No behaviour change; existing GUI tests pass
- `_reactive_color_wiring.py` reduces by ≥ 200 lines
- Error-handling path is tested once (via the factory), not per-dispatcher

**Effort estimate:** Low–Medium (1–2 h)

---

## Item 5 — Add wake-path integration test

**Files affected (new test file):**
- `tests/core/effects/reactive/test_reactive_wake_path_integration.py`

**Problem:**  
The idle-off → keystroke → restore holdoff re-seed → visual damp window sequence has been a
repeated regression site:

- 0.17.x: first post-wake pulse fired at full brightness
- 0.18.x: post-restore damp timer not re-seeded on keystroke after initial holdoff expired
- 0.23.7: re-seed path missed on the real wake path (vs. the test path)

There is currently no automated test that exercises this whole sequence. Each fix was
discovered manually during hardware testing and verified post-hoc with narrow unit tests
that only cover the final symptom, not the path.

**Target coverage:**

```
1. Engine starts, effect running
2. Tray calls dim_to_temp (screen dims)
3. Tray calls restore_brightness (screen wakes)
4. First keystroke arrives — verify:
     a. damp_pending is consumed and restore_damp_until is seeded
     b. pulse scale < 1.0 (damp is active)
     c. hardware brightness does NOT spike above pre-restore value
5. Keystroke arrives after damp window — verify:
     a. pulse scale == 1.0 (normal behaviour)
     b. restore_phase == NORMAL
6. Second screen dim/wake cycle — verify step 4 behaviour repeats
   (i.e. damp_pending is re-armed on every restore, not once)
```

**Acceptance criteria:**
- Test uses the real `_resolve_hw_brightness_with_pulse_mix` function, not mocks
- Engine state is a real `ReactiveRenderState` (or engine shim that includes it)
- Test is deterministic (no wall-clock `time.sleep`; use `monkeypatch` on `time.monotonic`)

**Effort estimate:** Medium (2–3 h; easiest after Items 1 and 3 land)

---

## Item 6 — Add pulse object pooling (optional / low priority)

**Files affected:**
- `src/core/effects/reactive/utils.py`
- `src/core/effects/reactive/_fade_loop.py`
- `src/core/effects/reactive/_ripple_loop.py`

**Problem:**  
A new `_Pulse` / `_RainbowPulse` object is allocated on every keypress and discarded when
the pulse expires. At normal typing speeds this is fine. Under burst input (held key repeat
at 30 Hz, macro pads, paste events) combined with high FPS renders, the per-frame GC
pressure becomes measurable.

**Target design:**  
A fixed-size ring buffer (capacity 64 or 128) of pre-allocated pulse slots. On keypress:
reclaim the oldest expired slot rather than allocating. Slots carry a `alive: bool` flag
rather than list removal.

**Note:** This is the lowest-priority item. Profile under real burst input before committing
to this change — Python's allocator handles small short-lived objects well and the GC
pause may not be observable at 60 FPS.

**Acceptance criteria:**
- No change to visual output
- `tracemalloc` snapshot shows < 5% pulse-allocation reduction under 30 Hz burst input
  (baseline measured before implementation)

**Effort estimate:** Medium (2 h for implementation, 1 h for profiling baseline)

---

## Implementation Order

| Priority | Item | Rationale |
|----------|------|-----------|
| 1 | Item 1 — ReactiveRenderState dataclass | Unblocks Items 3 and 5; reduces scattered state |
| 2 | Item 2 — _can_lift_hw_brightness predicate | Standalone, low effort, immediate readability gain |
| 3 | Item 3 — Restore phase enum | Depends on Item 1; removes dual-timer fragility |
| 4 | Item 5 — Wake-path integration test | Depends on Items 1 + 3; closes recurring regression gap |
| 5 | Item 4 — GUI dispatcher factory | Independent; can land any time |
| 6 | Item 6 — Pulse pooling | Only if profiling shows real pressure |

---

## Out of Scope

- Changing pulse visual behaviour (shape, color, timing)
- Changing hardware protocol or backend dispatch
- GUI layout changes to the reactive settings window
- Config schema changes
