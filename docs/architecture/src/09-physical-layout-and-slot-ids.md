# Physical Layouts and Canonical Slot IDs

## Goal

Keep visual-keyboard behavior stable across physical layout variants while
letting saved per-key data migrate away from legend-specific key IDs.

## Why this exists

Older KeyRGB flows treated the keymap as `key_id -> (row, col)` where `key_id`
was both the on-screen legend identity and the persistence key. That coupling
breaks down when:

- one physical slot can have different legends across locales
- optional keys are visible only on some layouts
- overlay tweaks and visibility should belong to the physical slot, not the
  current label
- one logical key may map to multiple matrix cells

## Current model

The reference keyboard model now has three related layers:

1. Physical layout variant selection
2. Canonical slot IDs for visible physical positions
3. Logical key IDs and labels used for user-facing names

Current owner modules:

- `src/core/resources/layouts/`
- `src/core/resources/layout_slots.py`
- `src/core/profile/profiles.py`
- `src/gui/perkey/profile_management.py`
- `src/gui/calibrator/app.py`
- `src/gui/reference/overlay_geometry.py`

## Rules

1. Saved setup should prefer canonical slot IDs.

Layout-slot visibility overrides, label overrides, and newer keymap ownership
belong to the slot identity first.

2. Legacy `key_id` data must still load.

Older profiles and calibrator state should continue to load without an external
migration step. Internally, load paths should normalize where possible.

3. Rendering still happens per physical cell.

Slot IDs determine which logical key is selected and configured. Color writes
still resolve to matrix cells in the final render path.

4. Layout selection is independent from backend probing.

Backends report matrix dimensions and hardware capabilities. Physical layout
selection belongs to the shared keyboard reference model and setup flow.

## Affected UX surfaces

- Keyboard Setup physical layout selection
- Keymap calibrator selection and assignment
- Per-key editor hit testing and overlay tweaks
- Reactive input fan-out from logical key to mapped cells

## Test strategy

- Layout catalog tests validate variant lookup and compatibility helpers.
- Profile storage tests validate legacy `key_id` compatibility and slot-ID
  persistence.
- Editor and calibrator tests validate slot selection, visibility, and overlay
  ownership.