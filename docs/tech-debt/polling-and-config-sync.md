# Polling and config sync debt

## Problem

The current runtime uses several polling loops and state-application paths to keep tray state, config state, and hardware state in sync. Each piece is individually understandable, but together they produce a system with hidden coupling and more moving parts than necessary.

## Evidence

- Config polling entrypoint:
  - `src/tray/pollers/config_polling.py`
- Supporting helpers and runtime flow:
  - `src/tray/pollers/_config_polling_core.py`
  - `src/tray/pollers/_config_polling_helpers.py`
  - `src/tray/pollers/hardware_polling.py`
  - `src/tray/pollers/icon_color_polling.py`
  - `src/tray/pollers/idle_power_polling.py`

`config_polling.py` already does some smart work, including mtime and digest checks, but the wider model is still primarily polling-driven.

## Risks

- Repeated state reconciliation logic grows across pollers.
- Effects, power state, and config state can interact in surprising orders.
- The code becomes harder to profile and harder to reason about under suspend, wake, and external config edits.

## Desired end state

- Fewer sources of truth for runtime decisions.
- More explicit event flow for config changes and power transitions.
- Polling retained only where Linux integration truly requires it.

## Suggested slices

1. Keep the current config digest protections, but isolate change detection from change application.
2. Move repeated config-apply decisions into a single transition layer.
3. Evaluate an event-driven config watch path for local environments where it is reliable enough.

## Buildpython hooks

- Existing signals:
  - File Size and LOC Check highlight growth in the poller modules.
  - Code Hygiene hotspot reports show whether exception-heavy polling logic is growing.
- Useful next increment:
  - Add a focused backlog or report section that tracks the largest poller modules over time, so growth becomes visible before behavior regresses.