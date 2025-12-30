# Legacy module boundaries

This document defines what “legacy” means in this repo and what belongs in `src/legacy/`.

## Scope

`src/legacy/` exists to:

- Keep older UI/config/effects code runnable for existing users.
- Avoid blocking new architecture work (tray/runtime, new backends, newer UI paths).
- Provide a place to quarantine higher-churn code that we do not want to extend.

## What is considered legacy today

- `src/legacy/gui_perkey.py`: older per-key UI.
- `src/legacy/effects.py`: legacy effect logic.
- `src/legacy/config.py` and `src/legacy/config_file_storage.py`: legacy config schema and persistence.

## Rules of engagement

- Bug fixes are OK.
- Keep behavior stable (avoid feature churn).
- Do not add new features to legacy modules unless there is no viable path in the new stack.
- Prefer building new functionality in non-legacy modules and optionally bridging at the UI level.

## Candidate migration paths (non-binding)

- Prefer `src/tray/` for runtime/tray responsibilities.
- Prefer `src/core/backends/` for hardware backends.
- Prefer `src/gui/` (non-legacy) for new UI work.

## Open questions

- Which legacy UI paths should be exposed in the tray (if any), and for how long?
- Do we want a formal deprecation policy (e.g., “legacy modules are frozen for 1 minor series”)?
