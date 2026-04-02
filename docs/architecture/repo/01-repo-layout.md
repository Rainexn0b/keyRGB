# Repo Layout

This page documents the repository directory structure rather than runtime
config locations.

## Application code

- `src/` - application source (core, tray app, and GUIs)
- `tests/` - pytest suite
- `buildpython/` - local build, quality, and release runner

## Supporting code and assets

- `scripts/` - installer and maintenance shell helpers
- `system/` - udev, desktop-integration, and other system-level assets
- `assets/` - bundled icons, screenshots, and related project assets

## Documentation

- `README.md` - end-user install, usage, and troubleshooting guide
- `docs/architecture/src/` - source and runtime architecture notes
- `docs/architecture/buildpython/` - buildpython architecture notes
- `docs/architecture/repo/` - repository-structure notes
- `docs/developement/` - contributor workflow, backend, layout, and maintenance notes
- `docs/bug-reports/` - deeper issue investigations and follow-up notes
- `docs/usage/` - user-facing workflow docs that extend the README

## Local or generated artifacts

These are typically generated locally during development:

- `.venv/`, `.venv_tmp/` - local virtual environments
- `.pytest_cache/`, `.ruff_cache/` - tooling caches
- `htmlcov/` - coverage HTML output
- `build/`, `dist/`, `buildlog/` - packaging and build outputs

## Vendor

- `vendor/` - upstream reference trees used for investigation and comparison
- `vendor/ite8291r3-ctl/` - vendored userspace reference backend
- `vendor/tuxedo-drivers-4.11.3/` - vendored kernel-driver reference tree

Some vendor subtrees are intentionally tracked in git, while others may still
be locally ignored depending on their purpose.