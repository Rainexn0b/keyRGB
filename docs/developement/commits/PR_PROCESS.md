# PR process (maintainers)

This document is for maintainers reviewing and merging pull requests.

## Before you merge

- Confirm the PR matches the project scope (ITE 8291 / ITE8291R3 focused).
- Confirm no hard-coded machine-specific paths or private references.
- Confirm user-facing changes have docs updates when needed (README or `docs/`).

## Minimal checks

Run locally:

```bash
python3 -m compileall -q src
pytest -q -o addopts=
```

Notes:
- Hardware tests are skipped unless `KEYRGB_HW_TESTS=1`.
- The CI workflow runs the same commands.

## Review checklist

- Safety:
  - No udev rules that make the device world-writable.
  - No background loops that can spin at 100% CPU.
  - No new USB calls outside the existing lock/serialization patterns.

- UX:
  - Tray app remains the single “USB owner” (no competing background controller).
  - Per-key editor writes config/profile data; tray applies it.

- Compatibility:
  - Avoid assuming KDE/Plasma-only behavior; autostart should be freedesktop-compatible.
  - Avoid hard requirements on optional dependencies (e.g. PyQt6).

## Handling hardware-dependent PRs

If a PR changes the USB protocol / controller logic:

- Ask for device details (USB ID, matrix size, laptop model) and clear reproduction steps.
- Prefer changes behind a safe default or a device-specific path.
- Ask the contributor to test with `KEYRGB_HW_TESTS=1` and to include logs.

## Merging

- Prefer squash merges for small PRs.
- Use regular merges when a PR has multiple meaningful commits that you want to preserve.
- After merge, verify the default branch is green in GitHub Actions.
