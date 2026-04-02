# Physical Slot ID Roadmap

Last updated: 2026-04-02

Related context:

- `docs/bug-reports/issue-4.md`
- `docs/bug-reports/issue-4.1.md`
- `src/core/resources/layouts/`
- `src/core/resources/layout_slots.py`
- `src/core/effects/reactive/input.py`

## Why this doc exists

KeyRGB already has a physical layout catalogue for ANSI, ISO, KS, ABNT, and JIS.
That solved the first-order geometry problem: the per-key editor and calibrator
can now show the correct physical keyboard family instead of hard-coding a
single ANSI-shaped overlay.

The next long-term problem is different:

- overlay geometry should be physical
- overlay labels should be locale-aware
- calibration and saved keymaps should stay stable
- reactive typing should not depend on QWERTY-looking key names forever

Today those concerns are still partly mixed together through `key_id` strings
such as `q`, `a`, `semicolon`, `nonusbackslash`, and so on.

Those IDs are doing too many jobs at once:

- physical slot identity in the overlay
- saved keymap identity
- reactive input identity
- visible user-facing legend text

That is workable for the current built-in layouts, but it is not the clean
long-term base for locale-specific legends such as QWERTZ, AZERTY, Nordic, or
other regional variants.

This note captures the intended long-term direction before implementation work
starts.

## Current state

### What already exists

Physical layout families are already catalogue-based:

- `src/core/resources/layouts/catalog.py` exposes the built-in physical layout list
- `src/core/resources/layouts/_api.py` resolves `auto` to a concrete layout ID
- `src/core/resources/layout_specs.json` uses inherited specs instead of fully duplicated layouts
- `src/core/resources/reference_defaults_specs.json` already follows the same inherited model for starter defaults

The per-key editor and calibrator already persist some layout-specific UI data:

- `src/core/config/layout_slots.py`
- `src/core/profile/profiles.py`
- `src/gui/perkey/editor.py`

That current `layout_slot_overrides` layer already proves two useful things:

1. Per-layout UI overrides belong with the per-key workflow, not global backend logic.
2. Small catalogue-style overrides are preferable to large duplicated definition files.

### What is still overloaded

The current overlay and reactive paths still treat letter-looking `key_id`
values as the stable identity.

Examples:

- layout specs define visible keys with IDs like `q`, `w`, `a`, `z`
- reactive input maps evdev names directly onto those IDs in `src/core/effects/reactive/input.py`
- keymaps persist logical key IDs against those overlay IDs

This creates a conceptual mismatch:

- the ID looks like a legend
- the system uses it like a physical slot

That mismatch is acceptable for the current QWERTY-oriented overlay model, but
it becomes awkward once different locale legend packs should share the same
physical keyboard geometry.

## Root problem

The repo needs a stable identity that represents a physical visual slot without
also implying the printed character on the keycap.

In other words, we need to decouple:

1. physical geometry
2. slot identity
3. displayed legend text
4. input or semantic binding

The current system cleanly separates only the first item.

## Long-term target model

The intended architecture is:

### 1. Physical layout catalogue

This remains what it is now:

- ANSI, ISO, KS, ABNT, JIS, and future physical families
- geometry, widths, row structure, special-key placement
- no locale-specific letter assumptions beyond a default fallback label

This should keep using the existing inherited catalogue model rather than large
full-layout snapshots.

### 2. Physical slot IDs

Each rendered key position should have a stable `slot_id` that means:

- this physical place on the overlay
- for this physical layout family
- independent from the currently displayed legend

Examples of the shape, not final names:

- `number_00`
- `top_01`
- `home_00`
- `shift_11`
- `bottom_04`
- `iso_extra_00`
- `jis_extra_02`
- `arrow_up`
- `numpad_7`

The exact naming should optimize for stability and maintainability, not for
pretty end-user labels.

Important rule:

- `slot_id` is the new long-term storage and UI identity
- visible labels become data attached to the slot, not the slot identity itself

### 3. Legend packs

Displayed text should come from a separate legend layer.

That layer should also be catalogue-based and inherited, not duplicated.

Suggested shape:

- one small base legend pack per physical family
- sparse override packs for regional variants
- optional per-user overrides for individual labels

Example families:

- `ansi-us`
- `iso-generic`
- `iso-uk`
- `iso-de-qwertz`
- `iso-fr-azerty`
- `iso-nordic`
- `abnt-br`
- `jis-jp`

The pack should answer:

- what text to draw for a given `slot_id`
- optionally what secondary text or symbol to show later

It should not define geometry.

### 4. Input or semantic bindings

Reactive typing and similar features should not eventually depend on
QWERTY-looking overlay IDs.

The long-term target is:

- evdev input maps into slot IDs or a thin slot-binding layer
- the overlay uses slot IDs directly
- displayed legends are resolved separately from the input mapping

This is especially important because current evdev names are effectively being
used as pseudo-slot IDs while still looking like printable legends.

## Why this is the right long-term solution

This model avoids the two bad extremes:

### Bad extreme 1: giant per-locale full JSON layouts

That would duplicate geometry and labels together for every variant and would
grow into a maintenance burden quickly.

### Bad extreme 2: using calibration or freeform drag-and-drop as the locale system

Calibration should answer physical LED assignment.
It should not become the built-in representation for German, French, Nordic, or
other standard keyboard legends.

The slot-ID plus legend-pack model keeps those concerns separate:

- geometry stays curated and testable
- legends stay catalogue-based and sparse
- user overrides remain possible
- calibration remains focused on LED mapping

## Proposed migration plan

The migration should be phased. This should not be a flag day rewrite.

### Phase 1: introduce slot IDs without breaking current layouts

Goal:

- add `slot_id` to the layout model while preserving existing `key_id` fields

Recommended steps:

1. Extend `KeyDef` and the layout spec loader so each visible key has both:
   - `slot_id`
   - legacy `key_id`
2. Generate deterministic slot IDs from row order only where safe, but prefer
   explicitly stored IDs in the specs for long-term stability.
3. Add helper APIs for:
   - resolving `slot_id -> rendered key`
   - resolving legacy `key_id -> slot_id` for the current layout
4. Keep all existing UI and storage behavior working through compatibility adapters.

Result:

- new code can start depending on slot IDs
- old code still works

### Phase 2: move UI layout identity to slot IDs

Goal:

- editor and calibrator selection, hit-testing, and override logic should use
  `slot_id` internally

Recommended steps:

1. Update the canvas and editor selection state to track selected slot IDs.
2. Replace `layout_slot_overrides` with a more general slot override model keyed
   by `slot_id`.
3. Keep compatibility reads for older `key_id`-based overrides during migration.

Result:

- overlay behavior no longer relies on label-looking IDs

### Phase 3: migrate keymap storage to slot IDs

Goal:

- keymaps should target stable physical slots, not semantic-looking key names

Recommended steps:

1. Extend profile load/save helpers to read legacy `key_id -> cells` maps and
   normalize them to `slot_id -> cells` in memory.
2. Write the new canonical storage as `slot_id -> list[(row, col)]`.
3. Keep a compatibility loader for existing saved profiles.

Result:

- calibration and saved mappings become physically anchored

### Phase 4: add legend packs

Goal:

- make overlay labels a separate catalogue layer

Recommended steps:

1. Create a `src/core/resources/legends/` package parallel to `layouts/`.
2. Add a small built-in legend pack catalogue.
3. Resolve legends by:
   - physical layout family
   - selected legend pack
   - optional user overrides
4. Keep default labels identical to current visible labels until a user selects
   a different legend pack.

Result:

- locale-specific overlay text becomes a data choice, not a geometry fork

### Phase 5: move reactive input to slot bindings

Goal:

- reactive typing should resolve to slot IDs instead of legacy letter IDs

Recommended steps:

1. Add an input binding table that translates evdev names into slot IDs for a
   given physical layout family.
2. Keep compatibility helpers for legacy `key_id` paths during rollout.
3. Update reactive tests to assert slot-based behavior explicitly.

Result:

- input, geometry, and legends are properly separated

## Catalogue approach for legends

The legend layer should follow the same design philosophy as the existing layout
catalogue:

- small curated catalogue entries
- inheritance instead of duplication
- explicit IDs instead of ad-hoc files

Suggested data shape:

- base pack per physical family provides every visible slot label
- derived packs only override changed slots

That keeps the total data small and reviewable.

Example:

- `iso-generic` supplies the full ISO-visible slot label set
- `iso-uk` overrides a handful of punctuation and symbol labels
- `iso-de-qwertz` overrides the Y/Z positions plus locale-specific punctuation
- `iso-fr-azerty` overrides the alpha block and selected symbol positions

This avoids the massive JSON-definition problem while still producing a proper
built-in catalogue.

## Compatibility rules

The migration should preserve these guarantees:

1. Existing profiles continue to load.
2. Existing keymaps continue to work without a manual migration step.
3. Existing physical layout selection remains valid.
4. Default visible labels remain unchanged until a legend pack is selected.
5. User overrides stay possible, but they become a thin layer on top of the new
   legend system rather than the core data model.

## Ownership and likely touch points

Current owner files likely involved in the migration:

- `src/core/resources/layout.py`
- `src/core/resources/layout_specs.json`
- `src/core/resources/layouts/_api.py`
- `src/core/resources/layout_slots.py`
- `src/core/config/layout_slots.py`
- `src/core/profile/profiles.py`
- `src/gui/perkey/editor.py`
- `src/gui/calibrator/app.py`
- `src/core/effects/reactive/input.py`

Likely new owner areas:

- `src/core/resources/legends/`
- a slot identity or slot binding helper near `src/core/resources/layouts/`

## Non-goals

This roadmap does not aim to:

- replace the current physical layout catalogue
- move physical layout ownership back into Settings
- turn calibration into a general locale editor
- solve every regional keyboard variant in one initial pass

## Recommended first implementation slice

The safest first slice is not legend packs yet.

It is:

1. add `slot_id` to the layout model
2. add compatibility helpers from legacy `key_id` to `slot_id`
3. make the editor and calibrator internally slot-aware while still rendering
   the same labels as today

That creates the stable long-term foundation first.

Only after that foundation exists should built-in legend packs be introduced.

## Closure criteria for this roadmap

This roadmap can be considered implemented when:

- visible key positions have stable physical slot IDs
- keymap storage uses slot IDs canonically
- overlay legends are resolved separately from slot identity
- built-in locale variants are represented as small catalogue-style legend packs
- reactive typing no longer depends on QWERTY-looking overlay IDs as its long-term identity layer