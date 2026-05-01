# Dim/Undim & Reactive Typing — Review Improvement Plan

> Generated: 2026-04-30
> Based on: full code review of dim/undim, reactive typing, idle-power, brightness, and power management subsystems
> See also: `docs/developement/optimisation/reactive-typing-improvement-plan.md` (original ReactiveRenderState consolidation plan)
> See also: `docs/developement/bug-ongoing/reactive-typing/reactive-typing-flicker-postmortem-2026-04.md`

---

## Summary of Findings

Overall score: **8.3/10**. The subsystems are well-designed with strong flicker prevention, thorough error resilience, and excellent documentation. The highest-value improvements concentrate on thread safety, completing the ReactiveRenderState migration, removing remaining attribute coupling, and parametrising hardcoded timing constants.

### Score breakdown

| Category | Score |
|---|---|
| Architecture & Design | 8.5/10 |
| Flicker Prevention & Brightness Correctness | 9/10 |
| Dim/Screen-Dim-Sync Logic | 8/10 |
| Error Handling & Resilience | 8.5/10 |
| Thread Safety | 7/10 |
| Performance | 8/10 |
| Testing | 8.5/10 |
| Documentation | 9/10 |

---

## Improvement Items

Items are ordered by **priority** (risk × effort inverse). Each includes affected files, problem description, target design, and acceptance criteria.

---

### Item 1 — Add thread safety to ReactiveRenderState transitions

**Priority:** P0 (highest — data race between render loop and idle-power thread)

**Files affected:**
- `src/core/effects/reactive/_render_brightness_support.py`
- `src/core/effects/reactive/_render_brightness.py`
- `src/core/effects/reactive/effects.py`
- `src/core/effects/reactive/render.py`
- `src/tray/pollers/idle_power/_transition_actions.py`
- `src/tray/pollers/idle_power/_actions.py`

**Problem:**

`ReactiveRenderState` attributes are read and written from two threads without synchronization:

1. **The idle-power polling thread** writes transition state via `_set_reactive_transition()`, seeds `_reactive_disable_pulse_hw_lift_until`, sets `_reactive_restore_damp_until`, flips `_dim_temp_active`, and updates `_reactive_restore_phase`.
2. **The reactive render loop** reads all of these fields every frame (~60 fps) via `resolve_brightness()` and `_resolve_reactive_transition_progress()`.

The multi-attribute transition seed in `_set_reactive_transition()` sets four fields (`from_brightness`, `to_brightness`, `started_at`, `duration_s`) non-atomically. A render frame could observe a partially-set transition (e.g., `from_brightness` from the old target and `to_brightness` from the new target), producing a one-frame brightness glitch.

Additionally, `_set_reactive_active_pulse_mix()` does a read-modify-write on `_reactive_active_pulse_mix` without locking. While CPython's GIL provides some protection for single-attribute reads/writes, the multi-field transitions are not GIL-safe because they require four separate attribute assignments.

**Target design:**

```python
# In ReactiveRenderState
@dataclass(slots=True)
class ReactiveRenderState:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    # ... existing fields ...

    def seed_transition(self, *, from_brightness: int, to_brightness: int,
                        started_at: float, duration_s: float) -> None:
        with self._lock:
            self._reactive_transition_from_brightness = from_brightness
            self._reactive_transition_to_brightness = to_brightness
            self._reactive_transition_started_at = started_at
            self._reactive_transition_duration_s = duration_s

    def read_transition(self) -> tuple[int, int, float, float] | None:
        with self._lock:
            if (self._reactive_transition_from_brightness is None
                    or self._reactive_transition_to_brightness is None):
                return None
            return (self._reactive_transition_from_brightness,
                    self._reactive_transition_to_brightness,
                    self._reactive_transition_started_at or 0.0,
                    self._reactive_transition_duration_s or 0.0)

    def update_pulse_mix(self, mix: float) -> None:
        with self._lock:
            self._reactive_active_pulse_mix = mix
```

The `dataclass(slots=True)` constraint means the `_lock` field needs to be excluded from `__init__` and managed separately, or `ReactiveRenderState` should be converted to a manual class with `__slots__`. An alternative is to use a single `threading.Lock` owned by the engine and acquired for all multi-field reads/writes.

**Minimal approach (recommended for first pass):**

Add a `threading.Lock` to `EffectsEngine` (next to `kb_lock`) and document that any code reading or writing multiple `ReactiveRenderState` fields must acquire `engine.reactive_lock`:

```python
# In engine.py
self.reactive_lock = threading.Lock()

# In transition actions — already inside kb_lock for some paths, but
# the render loop does not hold kb_lock during transition reads.
# Add reactive_lock around multi-field reads:
with engine.reactive_lock:
    transition = state.read_transition()
```

**Acceptance criteria:**
- All multi-field reads/writes of `ReactiveRenderState` in the render loop acquire `engine.reactive_lock`
- All multi-field writes in `_transition_actions.py` acquire `engine.reactive_lock` (can be nested inside `kb_lock` — since `kb_lock` is held for temp-dim transitions, and `reactive_lock` is never held for I/O, no deadlock risk)
- Single-field reads (e.g., `_reactive_active_pulse_mix`) can remain unlocked under documented GIL assumption
- A thread-safety test exercises concurrent transition seed + render read to confirm no spurious values
- All existing tests pass unchanged

**Effort estimate:** Medium (3–4 h; lock placement needs care to avoid deadlock)

---

### Item 2 — Complete the ReactiveRenderState migration; remove compat mirroring

**Priority:** P1 (medium — ongoing bug risk from dual-write)

**Files affected:**
- `src/core/effects/reactive/_render_brightness_support.py`
- `src/core/effects/reactive/effects.py`
- `src/core/effects/reactive/_render_brightness.py`
- `src/core/effects/engine.py`
- `src/tray/pollers/idle_power/_actions.py`

**Problem:**

The `ReactiveRenderState` dataclass was introduced (per the existing improvement plan) to consolidate scattered engine attributes. However, the migration is incomplete:

1. `_set_reactive_active_pulse_mix()` in `effects.py:108-112` writes to both `state._reactive_active_pulse_mix` (via `set_engine_attr`) and directly to `engine._reactive_active_pulse_mix` (via `setattr`). This dual-write is a bug risk — the two values can diverge if one write fails silently.

2. `set_engine_compat_attr()` in `_render_brightness_support.py:204-233` mirrors each `set_engine_attr()` write back to `engine.<name>` when `_compat_mirror_to_engine` is True. This hidden mirroring is hard to discover by reading the code and creates a maintenance burden.

3. `_set_engine_hw_brightness_cap()` in `_actions.py:120-138` directly sets `engine._hw_brightness_cap` and `engine._dim_temp_active` with `type: ignore[attr-defined]`, bypassing the `ReactiveRenderState` entirely.

4. `_transition_actions.py:151` and `_transition_actions.py:157` directly set `engine._dim_temp_active` and `engine.per_key_brightness` with `type: ignore[attr-defined]`.

**Target design:**

Remove `set_engine_compat_attr()` and the `_compat_mirror_to_engine` flag entirely. All reactive state should live on `ReactiveRenderState` and be accessed via `set_engine_attr()` → `ensure_reactive_state()`.

The explicit compat write in `_set_reactive_active_pulse_mix()` should be removed. If the `EffectsEngine` needs to read `_reactive_active_pulse_mix` for non-render purposes (e.g., GUI polling), it should read from `engine._reactive_state._reactive_active_pulse_mix` directly.

For `engine._dim_temp_active` and `engine._hw_brightness_cap`, move them onto `ReactiveRenderState` or create a dedicated `DimTempState` / `BrightnessCapState` dataclass. The idle-power code would then set these via accessor methods rather than direct attribute writes.

**Acceptance criteria:**
- `set_engine_compat_attr()` is removed
- `_compat_mirror_to_engine` is removed from `ReactiveRenderState`
- `_set_reactive_active_pulse_mix()` has a single write path
- `_set_engine_hw_brightness_cap()` uses `set_engine_attr()` or an accessor, not direct `engine.__dict__` writes
- `grep "type: ignore\[attr-defined\]" src/tray/pollers/idle_power/` returns zero results for state-setting code
- All existing tests pass unchanged

**Effort estimate:** Medium (3–4 h; needs coordinated changes across idle-power and reactive modules)

---

### Item 3 — Parametrise hardcoded timing constants

**Priority:** P1 (medium — configurability and maintainability)

**Files affected:**
- `src/core/effects/reactive/render.py`
- `src/core/effects/reactive/effects.py`
- `src/core/effects/reactive/_render_brightness.py`
- `src/tray/pollers/idle_power/policy.py`
- `src/tray/pollers/idle_power/_transition_actions.py`
- `src/tray/controllers/_power/_transition_constants.py`

**Problem:**

Critical timing and threshold constants are scattered as module-level magic numbers across multiple files. There is no single place to discover or adjust them:

| Constant | Value | File | Purpose |
|---|---|---|---|
| `_MAX_BRIGHTNESS_STEP_PER_FRAME` | 8 | `render.py:25` | Frame-to-frame brightness clamp |
| `_POST_RESTORE_PULSE_VISUAL_HOLDOFF_S` | 2.0 | `render.py:26` | Post-restore pulse-lift holdoff |
| `_POST_RESTORE_PULSE_VISUAL_MIN_FACTOR` | 0.35 | `render.py:27` | Minimum pulse scale during damp |
| `_PULSE_MIX_DECAY_STEP` | 0.34 | `effects.py:17` | Pulse mix per-frame decay |
| `_PULSE_MIX_RISE_STEP` | 0.45 | `effects.py:18` | Pulse mix per-frame rise |
| `_PULSE_MIX_INITIAL_RISE_STEP` | 0.18 | `effects.py:19` | Pulse mix first-keypress rise |
| `_FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S` | 0.30 | `effects.py:20` | First-activity HW-lift holdoff |
| `_FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S` | 2.0 | `effects.py:21` | Post-restore visual damp |
| `_UNIFORM_PULSE_HW_LIFT_STREAK_MIN` | 6 | `_render_brightness.py:17` | Frames before uniform HW lift |
| `_POST_TURN_OFF_RESTORE_SUPPRESSION_S` | 2.5 | `policy.py:7` | Suppress restore after turn-off |
| `_POST_RESUME_IDLE_ACTION_SUPPRESSION_S` | 10.0 | `policy.py:8` | Suppress idle actions after resume |
| `SOFT_OFF_FADE_DURATION_S` | 0.20 | `_transition_constants.py` | Fade duration for soft turn-off |
| `SOFT_ON_FADE_DURATION_S` | 0.42 | `_transition_constants.py` | Fade duration for soft turn-on |
| `SOFT_ON_START_BRIGHTNESS` | 1 | `_transition_constants.py` | Start brightness for wake fade |

The postmortem explicitly notes that the damp duration was too short initially and required adjustment. The `_POST_RESUME_IDLE_ACTION_SUPPRESSION_S = 10.0` is long enough to be noticeable by users who expect immediate keyboard restore on wake.

**Target design:**

Create a single constants module with clear documentation and grouping:

```python
# src/core/effects/reactive/_constants.py
#
# Reactive brightness timing constants.
#
# These values control visual smoothness during restores and transitions.
# They were tuned on ITE8291R3 hardware; different hardware may need
# different values.

# --- Brightness step guard ---
# Maximum brightness change per render frame before clamping.
# Prevents single-frame jumps (e.g. 3 -> 50) from concurrent writers.
MAX_BRIGHTNESS_STEP_PER_FRAME: int = 8

# --- Post-restore pulse visual damp ---
# Hardware-lift holdoff after restore: suppresses streak-gate bypass
# so the first few frames after wake don't spike to full brightness.
POST_RESTORE_PULSE_HW_LIFT_HOLDOFF_S: float = 2.0

# Minimum pulse scale factor during the visual damp window.
# 0.35 means the brightest pulse in the first ~2s after wake is
# scaled to 35% of its configured intensity.
POST_RESTORE_PULSE_VISUAL_MIN_FACTOR: float = 0.35

# --- Pulse mix rise/decay ---
PULSE_MIX_DECAY_STEP: float = 0.34      # per-frame decay when pulses end
PULSE_MIX_RISE_STEP: float = 0.45       # per-frame rise during active burst
PULSE_MIX_INITIAL_RISE_STEP: float = 0.18  # first keypress after idle

# --- Uniform backend HW-lift streak gate ---
# Number of consecutive frames with active pulse before a uniform-only
# backend is allowed to raise hardware brightness.
UNIFORM_PULSE_HW_LIFT_STREAK_MIN: int = 6

# --- First-activity hold-off ---
FIRST_ACTIVITY_PULSE_LIFT_HOLDOFF_S: float = 0.30
FIRST_ACTIVITY_POST_RESTORE_VISUAL_DAMP_S: float = 2.0
```

```python
# src/tray/pollers/idle_power/_constants.py
#
# Idle-power policy timing constants.
# These control debounce windows and suppression periods.

POST_TURN_OFF_RESTORE_SUPPRESSION_S: float = 2.5
POST_RESUME_IDLE_ACTION_SUPPRESSION_S: float = 10.0
```

```python
# src/tray/controllers/_power/_transition_constants.py
# (already exists — consolidate SOFT_* constants here or reference the new module)
```

Then replace all scattered references with imports from the constants module. Add `# see _constants.py` comments at each usage site for discoverability.

**Acceptance criteria:**
- A `grep -rn "_MAX_BRIGHTNESS_STEP_PER_FRAME\|_PULSE_MIX_DECAY_STEP\|_UNIFORM_PULSE_HW_LIFT_STREAK_MIN\|_POST_TURN_OFF_RESTORE_SUPPRESSION" src/` finds zero module-level definitions (they should be in constants modules)
- Each constant has a docstring explaining its purpose and units
- All existing tests pass unchanged (constants are imported, not changed)
- The constants module is explicitly documented in `docs/architecture/src/08-reactive-brightness-invariants.md` as the single source of truth for these values

**Effort estimate:** Low (1–2 h; mostly mechanical replacements)

---

### Item 4 — Fix backlight sensor resilience and add read timeouts

**Priority:** P2 (low—medium — currently works but has latent reliability risk)

**Files affected:**
- `src/tray/pollers/idle_power/sensors.py`

**Problem:**

`read_dimmed_state()` calls `Path.read_text()` and `Path.iterdir()` on `/sys/class/backlight` and `/sys/class/drm` without any timeout or signal safety. Under heavy I/O load (e.g., during suspend/resume), sysfs reads can block. The current exception handling catches `OSError` and `UnicodeError` but not `BlockingIOError` or `InterruptedError`.

Additionally, `_backlight_state_or_defaults()` uses `cast(_BacklightStateTray, tray)` and then directly assigns back to `tray._dim_backlight_baselines` and `tray._dim_backlight_dimmed`, creating hidden mutable state on the tray object. The `TrayIdlePowerState` dataclass exists but the sensor still writes directly to tray attributes.

**Target design:**

```python
import os
import signal

def _read_int_with_timeout(path: Path, timeout_s: float = 0.5) -> int | None:
    """Read an integer from a sysfs path with a timeout guard."""
    try:
        # Use os.open + os.read for better interrupt handling
        fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
        try:
            data = os.read(fd, 64)
        finally:
            os.close(fd)
        return int(data.decode("utf-8").strip())
    except (OSError, UnicodeError, ValueError, InterruptedError):
        return None
```

For the state coupling, migrate `read_dimmed_state()` to accept a `BacklightState` dataclass parameter that it mutates in place, rather than writing directly to tray attributes:

```python
@dataclass
class BacklightState:
    baselines: dict[str, int] = field(default_factory=dict)
    dimmed: dict[str, bool] = field(default_factory=dict)
    screen_off: bool = False
```

The polling loop would own one `BacklightState` instance and pass it to each sensor read. The tray no longer needs `_dim_backlight_baselines` / `_dim_backlight_dimmed` attributes.

**Acceptance criteria:**
- sysfs reads handle `InterruptedError` and `BlockingIOError`
- `BacklightState` is a dataclass, not tray attributes
- Existing sensor tests pass unchanged
- No new sysfs-related `AttributeError` paths introduced

**Effort estimate:** Low (1–2 h)

---

### Item 5 — Narrow exception handling in idle-power and reactive render paths

**Priority:** P2 (low—medium — currently over-broad)

**Files affected:**
- `src/tray/pollers/idle_power/_actions.py`
- `src/core/effects/reactive/_render_brightness_support.py`
- `src/core/effects/reactive/_render_runtime.py`

**Problem:**

Several catch blocks are broader than necessary:

1. `_call_runtime_boundary()` in `_actions.py` catches `_IDLE_POWER_RUNTIME_BOUNDARY_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)`. This includes `TypeError` and `ValueError`, which typically indicate programming errors (wrong argument types, wrong arities). Catching these silently makes bugs invisible at runtime.

2. `set_engine_attr()` / `read_engine_attr()` in `_render_brightness_support.py` catch `(AttributeError, TypeError, ValueError)` on every write/read. A typo in an attribute name would produce a silent fallback to the default value instead of an immediate failure.

3. The `_set_reactive_active_pulse_mix()` exception handler at `effects.py:111` catches `(AttributeError, TypeError, ValueError)` and logs via `logger.exception()` — which is better than silence, but still doesn't propagate the error.

**Target design:**

Split exception tuples into *recoverable* and *programming-error* categories. Programming errors should propagate in debug/development mode and be logged at `CRITICAL` in production (rather than silently swallowed):

```python
# Idle-power recoverable errors (external runtime conditions)
_RECOVERABLE_RUNTIME_ERRORS = (OSError, LookupError)

# Programming errors that should not be silently swallowed
_PROGRAMMING_ERRORS = (TypeError, ValueError)

def _call_runtime_boundary(fn, *, on_recoverable=None, ...):
    try:
        fn()
        return True
    except _RECOVERABLE_RUNTIME_ERRORS as exc:
        if on_recoverable is not None:
            on_recoverable(exc)
            return False
        _log_idle_power_exception(...)
        return False
    except _PROGRAMMING_ERRORS as exc:
        if os.environ.get("KEYRGB_DEV") == "1":
            raise  # propagate in development
        logger.critical("Programming error in idle-power boundary: %s", exc, exc_info=exc)
        return False
```

For `read_engine_attr` / `set_engine_attr`, `AttributeError` is genuinely recoverable (the attribute may not exist yet), but `TypeError` and `ValueError` should be logged at `WARNING` or `CRITICAL` rather than silently falling back to defaults. The current `error_default` pattern makes it impossible to distinguish "the attribute doesn't exist yet" from "we wrote the wrong type to it."

**Acceptance criteria:**
- `TypeError` and `ValueError` in `_call_runtime_boundary()` are no longer silently swallowed
- `read_engine_attr()` logs at `WARNING` level when the `error_default` fallback is hit (indicating something unexpected happened)
- A `KEYRGB_DEV=1` environment variable allows programming errors to propagate for development
- All existing tests pass unchanged (the test suite should not trigger programming-error paths with correct inputs)

**Effort estimate:** Medium (2–3 h; needs careful categorisation of each existing catch site)

---

### Item 6 — Add integration tests for full dim/undim cycle and concurrent access

**Priority:** P2 (medium — closes testing gap)

**Files affected (new test files):**
- `tests/tray/pollers/idle_power/runtime/test_idle_power_dim_undim_cycle_integration.py`
- `tests/core/effects/reactive/test_reactive_transition_thread_safety.py`

**Problem:**

The test suite is strong on unit tests but has no integration tests that exercise:

1. **The full dim → undim → reactive typing → restore cycle** end-to-end. The postmortem shows that bugs repeatedly appeared at the intersection of idle-power and reactive rendering — exactly where unit tests for each subsystem in isolation cannot catch cross-cutting regressions.

2. **Concurrent access to `ReactiveRenderState`** between the render loop and idle-power thread. No test validates that a transition seed from the idle-power thread and a concurrent frame read from the render loop produce consistent results.

3. **The `/sys/class/backlight` sensor with realistic sysfs layouts.** Sensor tests mock `Path` but don't exercise the hysteresis logic with realistic multi-backlight scenarios (e.g., a laptop with both `intel_backlight` and `amdgpu_bl0`).

**Target design:**

**Test 1 — Full dim/undim cycle:**

```python
def test_temp_dim_restore_cycle_no_flicker(mock_engine, mock_tray):
    """Exercise the full dim → temp-dim → restore → first keypress sequence
    and verify no brightness spike above the pre-dim baseline."""
    # 1. Start reactive effect at brightness=25
    # 2. Screen dims: apply dim_to_temp(target=5)
    # 3. Verify: resolve_brightness(hw) <= 5
    # 4. Screen wakes: apply_restore_brightness(target=25)
    # 5. First keypress: verify pulse scale < 1.0 (damp active)
    # 6. Wait 3s (simulated): verify pulse scale == 1.0 (damp expired)
    # 7. Second dim/wake cycle: verify step 5 behaviour repeats
```

**Test 2 — Transition thread safety:**

```python
def test_concurrent_transition_seed_and_render_read():
    """Seed transitions from one thread while reading from another.
    Verify resolve_brightness never returns a value outside the
    [from_brightness, to_brightness] range."""
    state = ReactiveRenderState()
    errors = []
    def seeder():
        for i in range(1000):
            state.seed_transition(
                from_brightness=i % 50,
                to_brightness=(i + 5) % 50,
                started_at=time.monotonic(),
                duration_s=0.42,
            )
    def reader():
        for _ in range(10000):
            # Read all four fields and verify consistency
            ...
    # Assert no out-of-range values observed
```

**Test 3 — Backlight hysteresis:**

```python
def test_backlight_hysteresis_dual_panel():
    """Simulate a laptop with both intel_backlight and amdgpu_bl0.
    When one panel dims below 90% and the other stays above 98%,
    verify dimming is detected (any panel dimmed triggers dim)."""
```

**Acceptance criteria:**
- Test 1 exercises the real `resolve_brightness()` and `_set_reactive_transition()` functions, not just mocks
- Test 2 uses real `ReactiveRenderState` objects with `threading.Thread` (not `asyncio`)
- Test 3 uses realistic sysfs directory tree structures (can use `tmp_path`)
- All three tests pass deterministically (no wall-clock `time.sleep`; use `monkeypatch` on `time.monotonic`)

**Effort estimate:** Medium (3–4 h for all three; test 2 depends on Item 1 landing)

---

### Item 7 — Add docstrings to ReactiveRenderState fields and core render functions

**Priority:** P3 (low — documentation quality)

**Files affected:**
- `src/core/effects/reactive/_render_brightness_support.py`
- `src/core/effects/reactive/render.py`
- `src/core/effects/reactive/_render_brightness.py`
- `src/core/effects/reactive/effects.py`

**Problem:**

The `ReactiveRenderState` dataclass has field names that are meaningful to an expert who has read the postmortem, but lack inline documentation:

```python
@dataclass(slots=True)
class ReactiveRenderState:
    _reactive_transition_from_brightness: int | None = None  # What state is this?
    _reactive_disable_pulse_hw_lift_until: float | None = None  # vs. _reactive_restore_damp_until?
    _reactive_restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.NORMAL  # Phase machine?
    _reactive_uniform_hw_streak: int = 0  # Why a streak counter?
```

Similarly, key functions like `_post_restore_visual_damp()`, `backdrop_brightness_scale_factor()`, and `_resolve_hw_brightness_with_pulse_mix()` have limited or no docstrings explaining the *why*.

**Target design:**

Add docstrings to `ReactiveRenderState` fields and key render functions:

```python
@dataclass(slots=True)
class ReactiveRenderState:
    """Consolidated state for reactive brightness rendering.

    Lifecycle:
    - Initialised in EffectsEngine.__init__ as ReactiveRenderState()
    - Reset on engine.stop() to clear stale timers
    - Seeded by idle-power transitions for dim/restore ramps
    - Read every frame by resolve_brightness() and the render loop
    """

    # --- Brightness transition animation ---
    # When set, resolve_brightness() animates from `_from` to `_to`
    # over `_duration_s` seconds starting at `_started_at`.
    # Cleared when the transition completes.
    _reactive_transition_from_brightness: int | None = None
    _reactive_transition_to_brightness: int | None = None
    _reactive_transition_started_at: float | None = None
    _reactive_transition_duration_s: float | None = None

    # --- Post-restore pulse damp ---
    # After an idle wake or temp-dim restore, hardware brightness is
    # low (e.g. 1) and needs to ramp up. During this ramp, reactive
    # pulses would appear as a bright flash if allowed at full intensity.
    # The holdoff delays the streak gate for hardware lifts, and the
    # damp reduces pulse visual scale during the window.
    _reactive_disable_pulse_hw_lift_until: float | None = None
    _reactive_restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.NORMAL
    _reactive_restore_damp_until: float | None = None

    # --- Uniform backend streak gate ---
    # Counts consecutive frames with active pulse on uniform-only backends.
    # Must reach UNIFORM_PULSE_HW_LIFT_STREAK_MIN (6) before HW lift is allowed.
    _reactive_uniform_hw_streak: int = 0

    # ... etc
```

**Acceptance criteria:**
- Every `ReactiveRenderState` field has a docstring or inline comment explaining its purpose
- `_post_restore_visual_damp()`, `backdrop_brightness_scale_factor()`, and `_resolve_hw_brightness_with_pulse_mix()` have docstrings explaining the "why"
- `_can_lift_hw_brightness()` existing docstring is reviewed and confirmed accurate

**Effort estimate:** Low (1–2 h; documentation only, no code changes)

---

### Item 8 — Reduce per-frame attribute reads in the render hot path

**Priority:** P3 (low — optimisation)

**Files affected:**
- `src/core/effects/reactive/_render_brightness.py`
- `src/core/effects/reactive/_render_runtime.py`

**Problem:**

`resolve_brightness()` reads ~10 engine attributes per frame via `read_engine_attr()`, which creates a fresh `attrgetter` each call. At 60fps, this is ~600 attribute lookups/second with exception-handling overhead. The `attrgetter` is not cached for these hot-path reads.

Similarly, `uniform_hw_streak()` reads from engine state and then `set_uniform_hw_streak()` writes back, requiring two separate attribute traversals per frame.

**Target design:**

Cache `attrgetter` instances for frequently-read attributes:

```python
# In _render_brightness_support.py
_cached_getters: dict[str, Callable] = {}

def _get_attrgetter(name: str) -> Callable:
    if name not in _cached_getters:
        _cached_getters[name] = attrgetter(name)
    return _cached_getters[name]
```

For `uniform_hw_streak`, combine read and write into a single `increment_uniform_hw_streak()` method on `ReactiveRenderState`:

```python
# In ReactiveRenderState
def increment_streak(self, *, reset: bool = False) -> int:
    if reset:
        self._reactive_uniform_hw_streak = 0
    else:
        self._reactive_uniform_hw_streak += 1
    return self._reactive_uniform_hw_streak
```

For `_scale_color_map()`, use a pre-allocated buffer when `transition_visual_scale < 0.999` instead of creating a new dict per frame:

```python
# In EffectsEngine or render context
self._color_map_buffer: dict[Key, Color] = {}

def _scale_color_map_into(dest: dict[Key, Color], src: Mapping[Key, Color], *, factor: float) -> None:
    f = max(0.0, min(1.0, factor))
    dest.clear()
    for key, rgb in src.items():
        dest[key] = (int(round(rgb[0] * f)), int(round(rgb[1] * f)), int(round(rgb[2] * f)))
```

**Acceptance criteria:**
- `resolve_brightness()` uses cached attrgetters for all engine attribute reads
- `uniform_hw_streak` read + write is combined into a single operation
- `_scale_color_map` uses an in-place buffer during transitions
- No visual or behavioural change
- Microbenchmark: `resolve_brightness()` shows < 5% improvement (this is a minor optimisation — the primary value is cleaner code, not performance)

**Effort estimate:** Low (1–2 h)

---

### Item 9 — Replace tray attribute coupling with typed state accessors

**Priority:** P3 (low — code quality)

**Files affected:**
- `src/tray/pollers/idle_power/_action_execution.py`
- `src/tray/pollers/idle_power/_actions.py`
- `src/tray/pollers/idle_power/sensors.py`
- `src/tray/pollers/idle_power/_polling_support.py`
- `src/tray/idle_power_state.py`
- `src/tray/protocols.py`

**Problem:**

The idle-power action code accesses tray state via loose attribute reads with `safe_int_attr()`, `safe_str_attr()`, and direct `hasattr()` / `getattr()` calls. The `IdlePowerTrayProtocol` exists but doesn't fully constrain the interface — action code still accesses `tray.engine`, `tray.config`, `tray.is_off` directly as untyped attributes with `type: ignore[attr-defined]` comments.

The `sensors.py` `_backlight_state_or_defaults()` function uses `cast(_BacklightStateTray, tray)` and then reads/writes mutable dict attributes on the tray. The `TrayIdlePowerState` dataclass was introduced to address this but the migration is incomplete — `sensors.py` still uses the old pattern.

**Target design:**

Migrate all idle-power state to go through `TrayIdlePowerState` accessors:

```python
# In idle_power_state.py (expanded)
@dataclass
class TrayIdlePowerState:
    dim_temp_active: bool = False
    dim_temp_target_brightness: int | None = None
    dim_backlight_baselines: dict[str, int] = field(default_factory=dict)
    dim_backlight_dimmed: dict[str, bool] = field(default_factory=dict)
    dim_screen_off: bool = False
    idle_forced_off: bool = False
    user_forced_off: bool = False
    power_forced_off: bool = False
    is_off: bool = False
    last_idle_turn_off_at: float = 0.0
    last_resume_at: float = 0.0

    # Convenience methods
    def reset_dim_state(self) -> None:
        self.dim_temp_active = False
        self.dim_temp_target_brightness = None
```

Then `sensors.py` would receive a `TrayIdlePowerState` object rather than the raw tray:

```python
def read_dimmed_state(state: TrayIdlePowerState, *, backlight_base: Path | None = None) -> bool | None:
    # Mutate state.baselines and state.dimmed directly
    ...
```

And action code would read from `state.dim_temp_active` instead of `read_idle_power_state_bool_field(tray, "_dim_temp_active", ...)`.

**Acceptance criteria:**
- All `_dim_*` and `_*_forced_off` tray attribute accesses are replaced by typed `TrayIdlePowerState` fields
- `_action_execution.py` no longer has `type: ignore[attr-defined]` comments for state fields
- `sensors.py` operates on `TrayIdlePowerState` instead of raw tray attributes
- Existing tests pass unchanged (they already mock the state layer)

**Effort estimate:** Medium (2–3 h; mostly mechanical refactoring)

---

## Implementation Order

| Priority | Item | Rationale | Depends on |
|---|---|---|---|
| 1 | Item 1 — Thread safety for ReactiveRenderState | Addresses data race; highest risk | None |
| 2 | Item 2 — Complete ReactiveRenderState migration | Removes dual-write bug risk | Item 1 (lock placement first) |
| 3 | Item 3 — Parametrise timing constants | Low effort, high discoverability gain | None (independent) |
| 4 | Item 6 — Integration tests | Closes regression gap | Item 1 (thread-safety test) |
| 5 | Item 4 — Backlight sensor resilience | Latent reliability fix | None (independent) |
| 6 | Item 5 — Narrow exception handling | Reduces silent bug swallowing | None (independent) |
| 7 | Item 7 — Docstrings | Documentation quality | Item 2 (after migration completes) |
| 8 | Item 8 — Reduce per-frame overhead | Minor optimisation | Item 2 (after migration completes) |
| 9 | Item 9 — Typed state accessors | Code quality | None (independent, can land any time) |

Items 1 and 2 are sequential. Items 3–9 are independent and can land in any order.

---

## Out of Scope

- Changing pulse visual behaviour (shape, color, timing)
- Changing hardware protocol or backend dispatch architecture
- GUI layout changes to dim-sync or reactive settings panels
- Config schema changes (the parametrised constants in Item 3 should stay code-level, not exposed to `config.json`)
- Rewriting the evdev input layer (the current design with synthetic fallback is correct)
- Replacing `attrgetter` with direct attribute access throughout (the defensive pattern exists for a reason — engine attributes may be missing during transitions)