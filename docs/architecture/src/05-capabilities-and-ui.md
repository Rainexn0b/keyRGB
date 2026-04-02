# Capabilities-driven UI (No UX changes)

## Goal

Keep the UX stable while preventing unsupported actions for a given backend.

This is explicitly **not** a redesign.

## Current state

`BackendCapabilities` exists and is returned by backends.

## Required behavior

The tray and GUIs should:

- Hide/disable per-key features when `per_key = False`
- Hide/disable hardware effects when `hardware_effects = False`
- Hide/disable palette-dependent items when `palette = False`

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
