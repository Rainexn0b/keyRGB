# Multi-device Routing and Software Targets

## Goal

Support auxiliary lighting devices without forcing them into keyboard-only tray,
GUI, or effects abstractions.

## Why this exists

KeyRGB started with a single keyboard-focused surface. Auxiliary devices such as
an ITE lightbar need their own state, menu actions, and software-effect routing
without destabilizing keyboard behavior.

## Current owner modules

- `src/tray/ui/menu_status.py`
- `src/tray/ui/menu_sections.py`
- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/controllers/software_target_controller.py`
- `src/core/diagnostics/device_discovery.py`
- `src/gui/windows/uniform.py`

## Current model

1. Device discovery can surface auxiliary devices separately from the keyboard.
2. Tray status rows act as selectable device contexts.
3. Non-keyboard contexts render their own menu sections.
4. Software effects can target either the keyboard only or all compatible
   devices.
5. Auxiliary per-profile state such as lightbar color and brightness stays
   distinct from the keyboard's primary state.

## Design rules

1. Keyboard logic stays authoritative for keyboard-only features.

Per-key editing, keymaps, and input-reactive behavior should not be diluted by
secondary-device concerns.

2. Auxiliary devices should plug in through explicit routing points.

Menu sections, controller handlers, and software-effect targets should be
selected by device type rather than ad-hoc conditionals spread through the main
keyboard path.

3. Uniform output is the default cross-device bridge.

Software effects may mirror a representative uniform output to compatible
auxiliary devices, but they should not force auxiliary devices into the
keyboard's per-key engine model.

## Current example

The lightbar path is the first auxiliary-device architecture consumer:

- tray context selection
- independent lightbar brightness and color config
- dedicated uniform-color target routing
- per-key editor lightbar placement overlay

## Testing

- Tray tests for context selection and per-context menu rendering
- Controller tests for lightbar actions and software-target policy
- GUI tests for target-aware uniform windows and lightbar placement controls