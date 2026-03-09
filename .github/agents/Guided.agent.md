# Guided Agent — KeyRGB

Purpose
- Short build-first routing guide for Copilot in this repo.
- KeyRGB is a Linux tray app + GUI suite for laptop keyboard lighting, with a strong focus on Tongfang/TUXEDO/Clevo/System76-style hardware paths.

Scope
- Backend fixes, tray/UI work, installer/udev/polkit integration, diagnostics, packaging, docs, and tests.
- Not for speculative hardware support claims or broad protocol additions without evidence.

## Precedence
- Failing tests/build output > repo scripts > `README.md` / `AGENTS.md` > this doc.
- `AGENTS.md` is the authoritative short summary for user-facing hardware/support guidance.
- Build logs live under `buildlog/keyrgb/`.
- Do not edit generated output in `buildlog/` or `htmlcov/`.
- Do not edit vendored reference code under `vendor/tuxedo-drivers-4.11.3/` unless explicitly asked.

## Fast start
1. Restate the task and identify the owning area before editing.
2. Put code in the nearest owner first:
   - `src/core/backends/<backend>/` → probing, capabilities, device logic
   - `src/core/diagnostics/` → snapshots, collectors, formatting
   - `src/core/effects/` → engine, fades, software/reactive effects
   - `src/tray/controllers/` → behavior and state transitions
   - `src/tray/ui/` → menu labels, capability gating, GUI launch wiring
   - `src/tray/app/` → wrapper methods and startup wiring
   - `src/tray/pollers/` → background loops and policy polling
   - `src/gui/windows/`, `src/gui/perkey/`, `src/gui/calibrator/`, `src/gui/settings/` → GUI work
   - `scripts/lib/` and `scripts/install_*.sh` → installer/uninstaller behavior
   - `src/tests/` → unit tests
3. Prefer sysfs/kernel-backed fixes first when applicable; USB fallback is second.
4. Prefer root-cause fixes over surface patches.
5. Preserve public entrypoints in `pyproject.toml` unless the task explicitly changes them.
6. Add or update tests when behavior changes.
7. Update `CHANGELOG.md` for user-visible changes.

## Repo-specific rules
- Backend priority matters: `sysfs-leds` is preferred over `ite8291r3` when a safe kernel path exists.
- Do not add new USB IDs to ITE backends without clear protocol evidence, diagnostics, and tests.
- `backend_caps` drives tray capability gating. Keep that model unless a task explicitly re-architects it.
- Graceful degradation should prefer hidden unsupported UI over dead controls, while still keeping required mode-switch actions available.
- Brightness-only sysfs backends are valid. Do not assume RGB support just because a keyboard backlight exists.
- The vendored TUXEDO driver tree is for investigation/reference, not routine editing.
- Prefer typed protocols and existing helpers (for example `safe_attrs`) over adding new scattered defensive conversions when touching tray/core glue.
- Keep Linux-first assumptions; this repo is not a cross-platform desktop app.

## Default execution loop
1. Identify the owning subsystem and affected backend path.
2. Read the nearest implementation and relevant tests first.
3. Implement the smallest root-cause fix.
4. Add or update targeted unit tests.
5. Run the smallest relevant validation.
6. Escalate to broader `buildpython` profiles when the change is cross-cutting.
7. Report changed files, validation, and any follow-up risk.

## Validation matrix
- Activate env: `source .venv/bin/activate`
- Quick targeted tests: `python -m pytest src/tests/test_...py`
- Standard project gate: `python -m buildpython --profile=ci`
- Full local quality gate: `python -m buildpython --profile=full --with-black`
- Gather full signal without stopping at first failure: `python -m buildpython --profile=full --with-black --continue-on-error`
- AppImage/package checks: `python -m buildpython --run-steps=14,15`
- Release gate: `python -m buildpython --profile=release`
- Logs: `buildlog/keyrgb/build-summary.md` and `buildlog/keyrgb/step-*.log`

## Common playbooks

### Backend / hardware triage
1. Check `README.md` and `AGENTS.md` first.
2. Collect `lsusb`, `/sys/class/leds`, and `keyrgb-diagnostics` when hardware support is unclear.
3. Prefer kernel/sysfs explanations for Clevo/TUXEDO/System76 paths.
4. Avoid claiming support is easy if the kernel LED export is missing.

### Tray / UX
1. Menu labels and gating live in `src/tray/ui/menu.py` and `src/tray/ui/menu_sections.py`.
2. Callback wrappers live in `src/tray/app/`.
3. Mode switching and fallback logic live in `src/tray/controllers/effect_selection.py`.
4. Update tray tests when menu structure, capability gating, or callbacks change.

### Installer / distro support
1. End-user install is AppImage-first.
2. Fedora / Red Hat is the primary tested path.
3. Debian / Ubuntu / Linux Mint and Arch-like flows are experimental / best-effort.
4. Keep package-manager work optional and avoid adding third-party repos automatically.
5. Installer changes usually belong in `scripts/lib/` plus `README.md` / `CHANGELOG.md`.

### GUI
1. Standalone windows live in `src/gui/windows/`.
2. Per-key editor and calibrator have dedicated packages.
3. When a backend lacks color/per-key support, prefer explanatory UI plus hidden unsupported tray entrypoints rather than broken flows.

## Tests and safety
- Hardware tests are opt-in only: `KEYRGB_HW_TESTS=1 python -m pytest -q -o addopts=`
- Do not require real hardware for normal unit tests.
- Preserve existing formatting conventions (Ruff/Black, 120-column line length).
- Target Python 3.10 semantics even if a newer interpreter is installed locally.

## References
- `AGENTS.md`
- `README.md`
- `docs/developement/Commands.txt`
- `docs/architecture/tongfang/00-index.md`
- `.github/agents/ReactiveTypingFlickerDebug.agent.md` (reactive typing / dim-sync flicker session context)
- `pyproject.toml`
- `CHANGELOG.md`

If anything is unclear, determine the owning backend, UI layer, installer layer, or failing build step before editing.

