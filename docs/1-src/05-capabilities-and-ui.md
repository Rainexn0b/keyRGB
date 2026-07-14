# Capabilities-driven UI

## Goal

Prevent unsupported actions for a given backend while keeping Static profile
state separate from animated Effect output.

## Current state

`BackendCapabilities` exists and is returned by backends.

## Required behavior

The tray and GUIs should:

- Hide/disable per-key features when `per_key = False`
- Hide/disable hardware effects when `hardware_effects = False`
- Hide/disable palette-dependent items when `palette = False`
- Expose profile-owned secondary lighting through the Lighting Profile Editor.
  Tray device rows are a separate, live-control context for capability-specific
  colour, brightness, and on/off actions; they do not select or replace profiles.
- Reuse the editor colour wheel for secondary lighting through an explicit per-row
  selector; a Keyboard selector restores the normal per-key target. Show secondary
  values in the wheel's decimal RGB format and provide a Setup button that restores
  the Lighting areas panel.
- Expose the Lighting Profile Editor when either the primary keyboard supports
  per-key colour or an available profile-compatible secondary route exists. Hide
  both the Lighting areas panel and its Setup button on keyboard-only systems.
- Put the `Include enabled lighting areas` toggle inside Software Effects and
  show it only when compatible secondary routes exist.
- Show an independent brightness submenu only for routes whose brightness policy
  is `independent`. Shared zones display `Brightness Override (follows Keyboard)`;
  unsupported routes do not receive a non-functional slider. Effect Speed remains
  global because secondary software output follows the same render clock.

If a user forces a backend via env and then clicks an unsupported action:

- do not crash
- show a clear log message (and optionally a UI message if the current UX already displays errors)

## Minimal integration points

- Tray menu builder: include/exclude submenus based on capabilities.
- Effect selection: prevent sending hardware effects to a backend that doesn’t support them.
- Per-key editor launcher: can remain available, but should gracefully show “not supported” if backend doesn’t support per-key.

## Testing

- Unit tests for menu construction logic using mocked capabilities.
- Ensure “no backend” state doesn’t crash menu build.
