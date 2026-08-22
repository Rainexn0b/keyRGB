# Repo Layout

This page documents the repository directory structure rather than runtime
config locations.

## Application code

- `keyrgb/` - application source (core, tray app, and GUIs)
- `tests/` - pytest suite
- `buildpython/` - local build, quality, and release runner

## Supporting code and assets

- `scripts/` - installer and maintenance shell helpers
- `system/` - udev, desktop-integration, and other system-level assets
- `assets/` - bundled icons, screenshots, and related project assets

## Documentation

- `README.md` - end-user install, usage, and troubleshooting guide
- `docs/1-src/` - source-code architecture for the `keyrgb/` package
- `docs/1-buildpython/` - buildpython design and operation
- `docs/1-repo/` - repository-structure notes
- `docs/2-usage/` - user-facing workflow docs that extend the README
- `docs/3-contributing/` - contributor workflow
- `docs/B-backend-guides/` / `docs/B-backend-audits/` - backend notes
- `docs/0-governance/lane-registry.md` - full documentation lane list

## Local or generated artifacts

These are typically generated locally during development:

- `.venv/`, `.venv_tmp/` - local virtual environments
- `.pytest_cache/`, `.ruff_cache/` - tooling caches
- `htmlcov/` - coverage HTML output
- `build/`, `dist/`, `buildlog/` - packaging and build outputs

## Vendor

- `vendor/` - upstream reference trees used for investigation and comparison
- `vendor/tuxedo-drivers-4.11.3/` - vendored kernel-driver reference tree

Some vendor subtrees are intentionally tracked in git, while others may still
be locally ignored depending on their purpose.