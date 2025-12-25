# Recent commits (most recent first)

## ee4468c — tray: tint icon based on active color (2025-12-25)
- Made the tray icon reflect the *currently applied keyboard color* instead of a static magenta.
- Representative color selection:
  - Uses averaged per-key colors for `perkey` mode.
  - Uses `config.color` for static effects.
  - Cycles a hue for multi-color effects (rainbow, wave, aurora, etc.) so the icon visibly "moves" with the effect.
  - Scales color by brightness and shows gray when off.
- Added a low-rate polling thread to refresh the icon for dynamic effects and avoid expensive per-frame updates.

## 033730c — packaging: add RPM + COPR publishing docs (2025-12-25)
- Added `packaging/rpm/keyrgb.spec` and `packaging/rpm/README.md` to support local RPM builds and COPR publishing.
- Added udev rule source at `packaging/udev/99-ite8291-wootbook.rules` (same rule used by `install.sh`).
- Added `scripts/copr-build-srpm.sh` helper to produce an SRPM suitable for COPR.
- Updated `README.md` to mention Fedora/RPM packaging.

## dc51a6f — buildpython: add reports, summary, and repo checks (2025-12-25)
- Added build summary output: `buildlog/keyrgb/build-summary.json` and `build-summary.md` at every run (including failures).
- Implemented a simple build "health" score and ASCII healthbar written to the summary and printed to the console.
- Added `Repo Validation` step (packaging/metadata checks) and hooked it into `ci`, `quick`, and `full` profiles.
- File size step now emits structured reports (`json/csv/md`) into `buildlog/keyrgb/` for easier PR review.
- Updated build system docs (`docs/architecture/02-Build-steps.md`, `03-Build-logs.md`) to mention reports and summary formats.

## be86263 / a0541fb / 27defea — build system & CI improvements (previous)
- Ported concepts from the reference JS build scripts into a small Python runner (`buildpython/`) with step profiles.
- Added steps for import validation, import scan, pip check, pytest, ruff (optional), code markers, and file size analysis.
- CI now runs `python -m buildpython --profile=ci` as the single source of truth.

---

### Notes / next steps
- The repo is currently tested locally (CI profile passes). Please re-run `python -m buildpython --profile=ci` after making changes that touch packaging or static analysis.
- If you want to publish to COPR, follow `packaging/rpm/COPR.md`; I can help with the COPR project setup and SRPM upload whenever you're ready.
- For testing the tray icon color behavior, start the tray (`./keyrgb` or `keyrgb`) and switch effects / per-key colors; the icon will change at a relaxed interval to reflect the applied colors.

(End of summary)
