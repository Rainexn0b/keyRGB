# Maintainability Debt Paydown Plan (2026-07-15)

## Purpose

Active backlog for maintainability and tech-debt paydown after the 2026-07-15
codebase review. Supersedes the prioritization narrative of older debt notes for
**what to do next**, while keeping historical detail under
`docs/Z-legacy/tech-debt/` and
`docs/I-implementation-plans/2026-04-19/architecture-and-maintainability-improvement-plan.md`.

## Conventions

- Priority: `P0` blocks safe iteration, `P1` high leverage, `P2` phased.
- Effort: `S` / `M` / `L`.
- Status: `todo` | `active` | `done` | `monitoring`.

## Inventory

| ID | Area | Issue | Priority | Effort | Status | Notes |
|---:|---|---|:---:|:---:|---|---|
| D1 | Tray runtime | Implicit/duck-typed tray flags; init-order hard to see | P0 | L | monitoring | Helpers + KeyRGBTray owner-backed properties; set helper skips dual-write on property-backed trays; idle runtime + restore policy fakes owner-backed; dual-write remains only for intentional bridge/sentinel tests; ownership map in `docs/1-src/13-tray-runtime-state-ownership.md` |
| D2 | Coordinators | Fat orchestration (tray app, config apply, power, some GUI) | P0 | L | monitoring | Config-apply gate + pure power-source debounce; software-target boundaries/profile split; settings_state split into reader/values/scheduler modules |
| D3 | Config/state | Dict-centric config; alias chains repeated | P1 | M | monitoring | Readonly secondary/effect-speed snapshot APIs; remaining raw readers are compatibility fallbacks |
| D4 | Backends | Duplicated HID find/open/identifier glue | P1 | M | monitoring | ite8291-style + ite8910-style find helpers shared; probe-result builders optional later |
| D5 | Polling | Config/hardware/idle pollers still tightly coupled | P1 | M | monitoring | Config-apply pure gates + hardware `_decisions` pure recovery/interval/persist classifiers (0.30.1) |
| D6 | Exceptions | Broad recoverable boundaries in hot paths (budgeted) | P1 | M | monitoring | Diagnostic/callback tuples narrowed; Step 19: 0 active broad-except, 54 annotated boundaries, 3 intentional waivers only |
| D7 | Tests | Strong units; thinner multi-component runtime flows | P1 | M | monitoring | Composite forced-off + idle dim/restore secondary + uniform/effect plan integrations (0.30.1); more optional |
| D8 | Packaging | `from src.*` import root | P2 | L | deferred | AppImage-first; no packaging pain observed; migrate only if reuse/install pain rises |
| D9 | Naming | Hard max-4 post-chip appendages rule | P2 | S | done | Canonical in `src/core/backends/README.md` |
| D10 | Docs | Large plan/legacy surface; onboarding cost | P2 | S | monitoring | This doc is the start-here index; 139 docs files are historical by design under lane registry |
| D11 | UI stack | Tk/pystray Wayland/tray edge cases | P2 | L | deferred | Product risk, not pure maintainability debt |
| D12 | Tooling | Keep buildpython debt baselines honest | P2 | S | monitoring | `--profile debt`; identification pass 2026-07-16 green |
| D13 | Layering | tray→gui theme detect; private cross-package imports | P2 | S | done | Theme detect moved to `src/core/theme` (0.30.1); tray→gui imports 0 |
| D14 | File size | Protocol/reactive/hardware-polling LOC buckets | P2 | M | monitoring | 0.30.1: reactive support debug split (~367); hardware poll ~446; chassis protocol 709 still device-local |
| D15 | Legacy secondary | `legacy_snapshot_from_config` markers (hygiene cleanup_hotspot=6) | P2 | S | deferred | Intentional v0.28→v0.29 compatibility path for issue #7 installs; do not remove while profiles still migrate |

## Phase plan

### Phase 0 — Guardrails (continuous)

- New backends must follow `src/core/backends/README.md` hard naming rules.
- Prefer aliases over renames for user-facing backend ids; keep secondary routes stable.
- Do not expand exception path budgets; only shrink after boundaries are narrowed.

### Phase 1 — State and orchestration (highest ROI)

1. **D1** Inventory remaining tray attributes beyond bootstrap state containers; group into typed namespaces (lighting / power / secondary / menu) without behavior change.
2. **D2 / D5** Expand config-apply pure plan objects; poller executes only. Mirror for power-event classification vs side effects.
3. Exit: one behavior change does not require a full fake tray/window surface.

### Phase 2 — Data and backend glue

4. **D4** Shared HID find/open/identifier helpers; migrate backends that copy the same glue. Protocol and packet code stay backend-local.
5. **D3** Typed config/snapshot accessors for hot maps (`secondary_device_state`, effect speeds).
6. Exit: a new experimental backend is mostly protocol + product IDs + registration.

### Phase 3 — Confidence

7. **D7** Integration tests for composite secondary + config apply + power restore (hardware-free).
8. **D6** Narrow exception boundaries after state is typed.
9. Exit: issue-class regressions (e.g. #7) have one multi-layer path, not only unit slices.

### Phase 4 — Optional cleanup

10. **D8** Revisit `src.*` packaging only if packaging/reuse pain appears.
11. **D9** Optional short renames only when human clarity wins; always keep aliases.
12. **D10** Keep this file current; archive stale plans under `Z-legacy` without deleting history.
13. **D11** UI stack only if tray reliability becomes a blocker.

## Near-term slices (ordered)

| Slice | Debt | Deliverable |
|---|---|---|
| S1 | D10 | This plan doc + index links |
| S2 | D4 | `shared_hidraw_probe` helpers; migrate ITE 8258 backends |
| S3 | D4 | Migrate remaining ite8291-style backends that reimplement the same glue |
| S4 | D1 | Document remaining tray attribute ownership; extract one more typed bag if cheap |
| S5 | D5 | Grow config-apply plan coverage (more branches pure) |
| S6 | D7 | One composite secondary + config-apply integration test expansion |

**Post-0.30.0 ordering:** residual work is tracked in
`docs/I-implementation-plans/2026-07-16/0.30.1-maintainability-follow-up-plan.md`
(W1 orchestration, W2 size hotspots, W3 multi-layer tests, CQ1 tray→gui theme).

## Related docs

- Backend naming hard rules: `src/core/backends/README.md`
- Older debt detail: `docs/Z-legacy/tech-debt/2026-03-31/`
- Architecture campaign: `docs/I-implementation-plans/2026-04-19/architecture-and-maintainability-improvement-plan.md`
- Shared USB debt note: `docs/Z-legacy/tech-debt/2026-03-31/backend-shared-usb-layer.md`

## Progress log

### 2026-07-15

- Added this plan.
- D9 naming hard rules recorded (max four post-chip appendages; coarse chassis tokens).
- D4 paydown slice:
  - Added `src/core/backends/shared_hidraw_probe.py`
  - Migrated `ite8258_zones_lenovo_legion`, `ite8258_perkey_chassis`,
    `ite8295_zones_lenovo_ideapad`, `ite8291_perkey`, and `ite8291_zones_clevo`
    find/open glue onto the shared helpers (zones keeps bcdDevice filtering local)
  - Identifier helper supports optional `usb_bcd_device`
  - Tests: shared probe unit + ITE 8291/8258/8295 suites (green)
- D5 paydown slice:
  - Extended `ConfigApplyPlan` with pure `apply_mode` (`perkey` / `uniform` / `effect`)
  - Post-fast-path execution uses `classify_apply_mode` instead of inline effect ifs
  - Unit tests cover mode classification
- D4 continued (ite8910-style):
  - Shared `find_matching_ite8910_style_hidraw_device` (injectable scanner for tests)
  - Migrated `ite8297_uniform` and `ite8233_none_chassis_lightbar_clevo` find glue
  - Open still routes through backend `_find_matching_supported_*` for monkeypatch seams
- D1 / S4: added tray runtime ownership inventory
  (`docs/1-src/13-tray-runtime-state-ownership.md`)
- S6: revalidated existing issue #7 composite integration/regression suites (green)
- D1 forced-off / dim-temp read migration:
  - Helpers: forced-off + `is_dim_temp_active` / `dim_temp_target_brightness` /
    `read_last_resume_at`
  - Migrated secondary scene, software targets, power-policy brightness, time
    scheduler, config forced-off skip, **hardware poller**, and **idle-power
    runtime** off direct private-attr reads
  - Unit tests: helper unit + full hardware/idle poller suites (green)
- D1 `_last_brightness` bag:
  - Owner field `TrayIdlePowerState.last_brightness` + `read_last_brightness` /
    `set_last_brightness`; bridged in `ensure_idle_state`
  - Migrated brightness-layer, config apply, power restore, idle restore paths
- D1 core straggler: `runtime_activation` power-forced-off read prefers legacy
  attr then owner (no tray import).
- D2/D5: pure `should_skip_config_apply_for_power_source_transition` used by
  `apply_from_config_once`.
- D2: extracted AC/battery debounce into pure `stabilize_power_source_state`; the
  `PowerManager` method now only owns mutable state and delegates the transition.
- D2: moved power-forced-off controller/owner detection into
  `management._manager_helpers.is_power_event_forced_off`.
- D3: exposed `Config.secondary_device_state_snapshot()` through the typed
  secondary-config facade; static-scene and config polling readers use it before
  raw `_settings` fallback.
- D3: exposed `Config.effect_speed_snapshot()` through the existing detached
  `EffectSpeedOverrides` boundary; support probe snapshots use it before raw
  `_settings` fallback.
- D7: `tests/tray/test_composite_config_apply_forced_off_integration_unit.py`
  (secondary static + forced-off + pure plan).
- D1 continued (owner-primary on real tray):
  - `KeyRGBTray` stores forced-off/dim/`last_brightness`/`last_resume_at` only on
    `tray_idle_power_state` via owner-backed properties
  - pre-bootstrap seeds the owner first, then the compatibility surface
  - core `runtime_activation` / power forced-off reads prefer legacy instance
    attr when present, else typed owner (KeyRGBTray properties have no instance
    dict entry)
  - dual-write helpers retained for duck-typed test fakes
- D2 continued:
  - software-target recoverable seams → `_software_target_boundaries.py`
  - profile reconcile/restore helpers → `_software_target_profile.py`
  - settings time-scheduler pure helpers → `gui/settings/_settings_scheduler.py`
- D1 continued (test fakes):
  - `tests/tray/fakes.py` owner-backed SimpleNamespace/MagicMock helpers
  - power-state/policy unit tests seed `TrayIdlePowerState` via helpers
- D2 continued (settings_state):
  - `_settings_reader.py` — source resolution + defensive readers
  - `_settings_values.py` — SettingsValues + load/apply
  - public `settings_state.py` remains the facade (datetime monkeypatch seam)
- D6 slice: narrowed `_RECOVERABLE_STRINGIFICATION_EXCEPTIONS` for menu-int
  parse (drop OS/Lookup classes that `str()` does not raise)
- D1 continued (broader fake migration):
  - time scheduler, composite integration, secondary static, menu adapters,
    menu brightness handlers, config forced-off, idle-power apply-action,
    hardware dim-temp tests use owner-backed fakes
- D6 continued:
  - idle action-key formatting: drop AttributeError/LookupError/OSError
  - tray icon config read: drop LookupError/OSError
  - tray logging boundary: drop LookupError
- D7: `test_clearing_forced_off_then_applies_secondary_and_keeps_plan_pure`
- D1 continued (dual-write reduction):
  - `set_idle_power_state_field` writes owner always; skips legacy setattr when
    the tray type already exposes the name as a property (`KeyRGBTray`)
  - more fakes: hardware brightness DummyTray, config loop misc, profile
    activation, hardware loop, issue#7 regression tray
- D6 continued: tray logger / software-target callback / notify-callback tuples
  drop LookupError; config apply-state fallback adds OverflowError only
- D1 continued (idle restore + wayland fakes):
  - `_idle_tray` helper in idle-power polling more unit; restore paths owner-backed
  - wayland idle iteration trays use `make_owner_backed_simple_tray`
  - hardware loop dim-temp BadInt case owner-backed
- D6 continued: UI refresh/menu callbacks + secondary runtime boundary drop
  LookupError; per-key status drops OSError
- D1 continued (dim/restore + forced-off fakes):
  - idle dim_to_temp / restore-gate trays owner-backed
  - config forced-off menu-failure uses set helper
- D6 continued: event-log, engine-attr-sync, brightness-layer drop LookupError
- D1 continued: idle runtime `_make_tray` owner-backed; restore policy clear-path
  uses fakes; owner-only missing-legacy restore test drops instance attrs
- D6 continued: icon-poll + tray backend-select drop LookupError (power-policy
  keeps LookupError for tested UI callback failures)
- D1 continued: reactive dim-sync lock tests owner-backed; power-manager
  battery-saver/event MagicMocks attach real `TrayIdlePowerState` for forced-off
- D6 continued: notification backend + idle-power diagnostic runtime tuples drop
  LookupError
- D1 continued: config apply perkey/misc `_mk_tray*` helpers owner-backed
- D6 continued: profile menu callback + enable_user_mode save tuples drop
  LookupError
- D1 continued: power-manager event integration/handlers attach real
  `TrayIdlePowerState`; config apply last_brightness asserts owner field
- D6 continued: config persist sync tuple drops LookupError
- D1/D6 audit: remaining direct legacy-flag fixtures are intentional
  bridge/sentinel coverage; remaining broad runtime tuples are concentrated in
  hardware, long-running polling, backend/effect, or tested UI-failure seams
  and were left unchanged without a distinct degraded-behavior contract.
- Gate hygiene: removed stale unused imports/locals exposed by the full Ruff
  gate across existing test modules.
- D1 final dual-write decision: production `KeyRGBTray` writes are already
  owner-only because property-backed attrs bypass the compatibility setattr.
  Keep the duck-typed dual-write bridge and `sync_idle_power_state_field` for
  legacy/external seams and sentinel tests; a global removal would change that
  tested fallback contract without reducing production storage.
- Identification wave (folder structure / imports / residual debt):
  - Layering clean: `core → tray|gui` = 0; `gui → tray` = 0; architecture
    validation 0 findings. Only `tray → gui` is theme detect (1 import).
  - Middle-man / unreferenced-file candidates: 0. TODO/FIXME/HACK: 0.
  - Exception transparency: 0 active broad-except (3 intentional waivers).
  - Remaining signals are deferred product/compat/size items (D8, D11, D13–D15),
    not release-blocking maintainability debt.
  - Verdict: identified debt wave exhausted; safe to proceed to publish.

Verification: full suite `3055 passed, 1 skipped`; full Ruff clean;
`git diff --check` clean; Steps 5/6/12/16/17/19 passed (health 100/100);
Step 19: 0 active broad-except findings, 54 annotated boundaries.
