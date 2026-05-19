# Lighting Layer Model Review (2026-05)

## Purpose

This note captures the canonical lighting model for KeyRGB before further
power-profile and tray refactors.

It is based on the intended behavior:

1. Base lighting is the source of truth for deck colors.
2. Brightness is a separate policy layer.
3. App effects are a separate user-selected layer and should not be rewritten
   by base-profile or brightness policy changes.

This document also records where the current codebase still violates that
model and what refactor slices are needed to align with it.

## Execution status (2026-05-18)

Implemented in code:

- slice 2: base-profile activation no longer rewrites `config.effect`
- slice 3: config polling now tracks base per-key signatures independently of
  the selected effect
- slice 4: runtime `effect = none` now means “render the base layer,” including
  static per-key base rendering when `per_key_colors` exist
- slice 5: manual tray profile activation and power-source profile activation
  now share one runtime activation coordinator
- slice 6: brightness-layer state ownership is now aligned across tray power
  policy, time scheduler, and the core power-manager fallback
- slice 6 follow-up: scheduler-window brightness resolution and AC/DC
  brightness composition now share one canonical resolver in
  `src/core/brightness_layers.py`

Still remaining:

- consolidate any future brightness-policy behavior changes through the same
  shared seams instead of reintroducing per-surface branches

Compatibility note:

- persisted `effect = "perkey"` is still accepted as a legacy alias for static
  base rendering, but new base-profile writes no longer depend on it
- the tray-side power-policy and time-scheduler brightness paths now also share
  one layered brightness helper
- the scheduler-window resolver in `src/core/brightness_layers.py` is now the
  canonical place for time-scheduler base/reactive selection, defer-to-power
  decisions, and AC/DC base-brightness composition
- the core fallback path still keeps a simpler engine-write surface than the
  tray path because it has no tray lifecycle or restart semantics available,
  but it now follows the same layer-aware state sync rules

## Canonical 3-layer model

### Layer 1: Base lighting

The base layer owns the underlying color surface that should exist even when no
effect is running.

Responsibilities:

- active per-key profile selection
- persisted `per_key_colors`
- persisted fallback uniform color for devices or modes without a per-key base
- profile activation from the per-key editor, tray profile menu, and AC/battery
  power-source switching

Rules:

- base-layer changes must not rewrite the user-selected effect
- base-layer changes must be observable even while a software or hardware
  effect is active
- “show the profile colors with no app effect” is a valid runtime state

### Layer 2: Brightness policy

The brightness layer owns environment-driven brightness policy applied on top
of the base layer.

Responsibilities:

- time-of-day brightness changes
- AC/battery brightness changes
- idle dim / idle restore / screen-dim sync
- last-known brightness restore

Rules:

- brightness policy must not rewrite the base profile selection
- brightness policy must not rewrite the selected effect
- effect-local intensity knobs belong to the effect layer, not to this layer

### Layer 3: Effect layer

The effect layer owns the user-selected runtime effect and its parameters.

Responsibilities:

- selected effect identity
- hardware effect selection
- software effect selection
- effect parameters such as speed, direction, reactive/manual color, reactive
  pulse brightness, reactive trail, and similar effect-specific settings

Rules:

- effect `none` means “no tertiary effect; render the base layer as-is”
- effects that define their own colors, such as rainbow-style effects, may
  ignore layer 1 colors
- effects that build on a backdrop, such as reactive typing, should consume the
  base layer instead of replacing its state model

## Review summary

The codebase is not far from this model conceptually, but the persisted config
still overuses `config.effect` as both:

- the selected runtime effect
- the current static rendering mode
- an implicit proxy for whether a per-key base exists

That overloading is the root cause of most of the recent AC/battery transition
complexity.

### Current scope estimate

This is a moderate refactor, not a one-file cleanup.

Expected hotspot count:

- runtime code: about 10-15 files
- UI/menu/icon state files: about 4-6 files
- tests: about 12-20 files

The good news is that most of the work is architectural untangling, not new
backend research.

## Findings

### 1. `config.effect` is overloaded across all three layers

Relevant files:

- `src/core/profile/_profile_apply_ops.py`
- `src/core/config/config.py`
- `src/tray/controllers/effect_selection.py`
- `src/tray/controllers/lighting_controller.py`
- `src/tray/ui/_menu_callbacks.py`

Evidence:

- per-key profile activation persists `effect = "perkey"` in
  `src/core/config/config.py`
- effect selection rewrites `config.effect` between `"none"`, `"perkey"`,
  hardware effects, and software effects in
  `src/tray/controllers/effect_selection.py`
- tray UI checked-state logic reads `config.effect` directly in
  `src/tray/ui/_menu_callbacks.py`

Why this violates the model:

- layer 1 profile activation should not rewrite layer 3 selected effect
- layer 3 menu state should not be inferred from layer 1 base persistence

Impact:

- power-profile changes need compensating logic to preserve the real running
  effect
- runtime code now has to prefer `engine.current_effect` over persisted config
  in some paths
- future maintainers can easily reintroduce regressions by trusting
  `config.effect`

### 2. “No effect” currently means different things in different places

Relevant files:

- `src/tray/controllers/effect_selection.py`
- `src/tray/controllers/lighting_controller.py`
- `src/tray/ui/_menu_callbacks.py`

Evidence:

- selecting `"none"` in `effect_selection.py` can flip back into persisted
  `"perkey"` if per-key colors exist
- the code still treats `"perkey"` as a rendering mode instead of a pure base
  state

Why this violates the model:

- under the 3-layer model, “no effect” should mean “render base only”
- whether the base is per-key or uniform should not require a separate effect
  identity

Impact:

- static per-key rendering is modeled as an effect instead of a base-layer
  presentation
- effect menus and transition logic need special-case branches for `"perkey"`

### 3. Config polling only tracks per-key signatures when `effect == "perkey"`

Relevant files:

- `src/tray/pollers/config_polling_internal/_config_apply_state.py`
- `src/tray/pollers/config_polling_internal/_apply_callbacks.py`

Evidence:

- `perkey_sig` is only read when `effect == "perkey"` in
  `_config_apply_state.py`

Why this violates the model:

- base-layer changes should matter regardless of the active effect
- a reactive backdrop should see base-profile changes even while the effect
  remains reactive

Impact:

- base-layer edits can be invisible to config polling if the current effect is
  reactive or another non-`perkey` mode
- this is one of the strongest reasons to separate base-state signatures from
  effect-state signatures

### 4. Power-source profile activation and manual profile activation use
different orchestration paths

Relevant files:

- `src/core/power/management/manager.py`
- `src/tray/controllers/menu_adapters/__init__.py`

Evidence:

- the power manager activation path marks recent transitions and attempts an
  in-place transition
- the tray menu adapter activation path still applies the profile and restarts
  the current effect directly

Why this violates the model:

- layer 1 activation should have one canonical orchestration path
- power-source and manual profile activation should not drift semantically

Impact:

- recent fixes live in one path but not the other
- maintainers have to reason about two different profile-activation behaviors

### 5. Brightness policy is conceptually separate, but writes are duplicated
across multiple owners

Relevant files:

- `src/tray/pollers/time_scheduler.py`
- `src/tray/controllers/_power/_lighting_power_policy.py`
- `src/core/power/management/_manager_brightness_execution.py`
- `src/tray/pollers/idle_power/_actions.py`

Evidence:

- time scheduler writes `brightness`, `perkey_brightness`, and sometimes
  `reactive_brightness`
- tray power policy also writes `brightness` and `perkey_brightness`
- core power manager mirrors brightness into config separately

Why this violates the model:

- the layer concept is right, but the write orchestration is still fragmented
- brightness policy should be centralized enough that “who owns the final
  persisted brightness value” is obvious

Impact:

- fade behavior and config persistence policy are harder to keep consistent
- effect-local and global brightness semantics are easy to mix up

### 6. Per-key transition logic is duplicated between tray helpers and config
polling

Relevant files:

- `src/tray/controllers/_lighting_controller_helpers.py`
- `src/tray/pollers/config_polling_internal/_apply_callbacks.py`

Evidence:

- both modules implement “apply per-key with optional reassert / hidden restore”
  logic
- the tray helper path already handles hardware blank hints; the config-poller
  path does not share that exact implementation

Why this matters:

- backend quirks should not require parallel fixes in two near-identical
  control paths

Impact:

- higher regression risk for future `ite8291r3` or per-key backend fixes

## Recommended target model

### Persisted state

Recommended long-term split:

- `base_*`
  - base surface identity and data
  - active per-key profile name
  - `per_key_colors`
  - fallback uniform base color if needed
- `brightness_*`
  - global/base brightness
  - external brightness policy settings
- `effect_*`
  - selected effect name
  - effect parameters

Minimum rule even before a full schema change:

- stop letting base-profile activation rewrite `config.effect`

### Runtime composition

Recommended runtime order:

1. Resolve base surface.
2. Resolve brightness policy.
3. Run selected effect over the base surface.

Practical meaning:

- if effect is `none`, render the base surface directly
- if effect is reactive, use the base surface as the backdrop
- if effect is rainbow-style, the effect may replace base colors but still
  respects the selected effect identity and brightness policy boundaries

## Suggested refactor slices

### Slice 1: Canonical state vocabulary

Goal:

- agree on the terms base layer, brightness layer, and effect layer
- document them here and in code comments

Expected code change:

- docs only or very small comments

### Slice 2: Stop profile activation from mutating selected effect

Goal:

- make per-key profile activation update layer 1 only

Primary files:

- `src/core/profile/_profile_apply_ops.py`
- `src/core/config/config.py`
- `src/core/power/management/manager.py`
- `src/tray/controllers/menu_adapters/__init__.py`

Notes:

- if backward compatibility is needed, treat persisted `"perkey"` as a legacy
  alias during migration rather than as the long-term model

### Slice 3: Make config polling track base state independently of effect state

Goal:

- detect `per_key_colors` changes regardless of selected effect

Primary files:

- `src/tray/pollers/config_polling_internal/_config_apply_state.py`
- `src/tray/pollers/config_polling_internal/_apply_callbacks.py`
- `src/tray/pollers/config_polling_internal/core.py`

### Slice 4: Redefine “no effect” as “render base only”

Goal:

- remove the need for `config.effect = "perkey"` as the static-base sentinel

Primary files:

- `src/tray/controllers/effect_selection.py`
- `src/tray/controllers/lighting_controller.py`
- `src/tray/ui/_menu_callbacks.py`
- `src/tray/ui/icon/__init__.py`

### Slice 5: Unify manual and power-source profile activation

Goal:

- one canonical base-profile activation flow

Primary files:

- `src/core/power/management/manager.py`
- `src/tray/controllers/menu_adapters/__init__.py`

### Slice 6: Centralize brightness apply orchestration

Goal:

- keep global brightness policy separate from effect-local intensity

Primary files:

- `src/tray/pollers/time_scheduler.py`
- `src/tray/controllers/_power/_lighting_power_policy.py`
- `src/core/power/management/_manager_brightness_execution.py`
- `src/tray/pollers/idle_power/_actions.py`

## Test implications

Tests that should exist after the refactor:

- base-profile activation does not rewrite selected effect
- base-layer config changes are detected while reactive effects are active
- `effect = none` renders the base layer correctly for both uniform and per-key
  bases
- manual tray profile activation and AC/battery profile activation follow the
  same orchestration path
- brightness policy updates do not mutate effect selection

## Release guidance

For the current codebase, the recent AC/battery work is functional but still
architecturally compensating for `config.effect` overloading.

Recommendation before expanding this area further:

- treat this document as canonical
- finish at least slices 2 and 3 before broadening power-profile functionality
- consider slice 4 the real semantic cleanup that makes the model durable
