# Legacy module boundaries

As of 2026-01-01, `src/legacy/` was removed and its remaining active code paths were moved into `src/core/`.

## Scope

Historically, `src/legacy/` existed to:

- Keep older UI/config/effects code runnable for existing users.
- Avoid blocking new architecture work (tray/runtime, new backends, newer UI paths).
- Provide a place to quarantine higher-churn code that we do not want to extend.

## What was considered legacy

- Older per-key UI (replaced by `src/gui/perkey/`).
- Effects engine (now `src/core/effects/engine.py`).
- Config schema and persistence (now `src/core/config.py` and `src/core/config_file_storage.py`).

## Rules of engagement

- Bug fixes are OK.
- Keep behavior stable (avoid feature churn).
- Do not add new features to legacy modules unless there is no viable path in the new stack.
- Prefer building new functionality in `src/core/` and `src/gui/`.

## Candidate migration paths (non-binding)

- Prefer `src/tray/` for runtime/tray responsibilities.
- Prefer `src/core/backends/` for hardware backends.
- Prefer `src/gui/` (non-legacy) for new UI work.

## Open questions

- Which legacy UI paths should be exposed in the tray (if any), and for how long?
- Do we want a formal deprecation policy (e.g., “legacy modules are frozen for 1 minor series”)?
