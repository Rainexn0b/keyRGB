# Repo layout

This page documents the *repository* directory structure (as opposed to runtime config locations).

## Source code

- `src/` — application source (core, tray app, and GUIs)
- `src/tests/` — unit tests (pytest)

## Documentation

- `docs/` — project documentation
  - `docs/usage/` — end-user usage docs
  - `docs/architecture/` — technical architecture notes
  - `docs/development/` — contributor/process notes
  - `docs/developement/` — legacy spelling (kept as a redirect for compatibility)

## Local / generated artifacts

These directories are typically generated locally and should not be committed:

- `.venv/`, `.venv_tmp/` — local virtual environments
- `htmlcov/` — coverage HTML output
- `.pytest_cache/`, `.ruff_cache/` — tooling caches
- `dist/`, `build/`, `buildlog/` — packaging/build outputs

## Vendor

- `vendor/` — upstream reference clones / vendored deps (not shipped; gitignored)
