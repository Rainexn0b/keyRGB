# Issue 7 — Second review: v0.29.1 flash-then-off regression

- **Date:** 2026-07-15
- **Role:** Second reviewer (post GPT-sol-ultra diagnosis and applied diff)
- **GitHub issue:** https://github.com/Rainexn0b/keyRGB/issues/7
- **Base revision reviewed against:** `main` @ `ab31e73` (Release v0.29.1)
- **Scope:** Unstaged working-tree changes implementing the dual-seam fix

## 1. Executive verdict

**Approve with residual hardware risk.**

- The dual-seam diagnosis matches the reporter’s v0.29.1 symptom
  (*“changing modes flashes the lights and then they all turn off”*).
- The applied code changes are proportionate root-cause fixes for that path.
- Focused automated tests for the intended contracts are green.
- **Do not claim issue #7 fully closed** until the reporter revalidates on
  Lenovo Legion Pro 7 16IAX10H (83F5 / `0x048d:0xc197`).
- No merge-blocking defect was found in the reviewed patch itself.

| Question | Answer |
|---|---|
| Root-cause diagnosis sound? | **Yes** |
| Diff addresses the 0.29.1 flash-then-dark symptom? | **Yes, by design** |
| Critical oversight in the patch? | **No merge-blocking defect found** |
| Ready to call issue #7 fully done? | **No** — hardware confirmation still required; older #7 workstreams are separate |
| Larger redesign required? | **No** — coordinator + mirror gating is proportionate |

## 2. Reporter context (what this review targets)

### 2.1 Latest regression (primary target of this diff)

Reporter on v0.29.1:

> Something is really broken in 0.29.1... changing modes flashes the lights and
> then they all turn off.
> I switched back to 0.28.2 for now.

### 2.2 Hardware identity

- Product: Lenovo Legion Pro 7 16IAX10H (`83F5`)
- Primary lighting USB ID: `048d:c197` — ITE Device(8258)
- Also present: `048d:c193` (Lenovo Lighting; not the keyboard RGB path under review)
- Surfaces: keyboard + lid logo + neon strip + vents on one composite controller

### 2.3 Earlier #7 workstreams (not re-fixed by this diff)

These were addressed (or partially addressed) in prior releases and are **out of
scope** for the 2026-07-15 dual-seam patch, except as residual product status:

| Workstream | Approx. release | Status note |
|---|---|---|
| Experimental backend detection | 0.25.8+ | Available when experimental backends enabled |
| hidraw permissions / udev | 0.25.10, 0.28.2 | Rules updated; full install required |
| Keyboard matrix / keymap | 0.27.1 | Patched from support-bundle evidence |
| Secondary routes (logo/neon/vent) | 0.27–0.28 | Detected; animated “all compatible” worked earlier than static |
| Secondary static + profile editor | 0.29.0 / 0.29.1 | Introduced the regression class under review |

## 3. Files in the reviewed diff

### Code

- `src/core/backends/ite8258_perkey_chassis_logo_neon_vent_lenovo_legion/profile_coordinator.py` (**new**)
- `src/core/backends/ite8258_perkey_chassis_logo_neon_vent_lenovo_legion/backend.py`
- `src/core/backends/ite8258_perkey_chassis_logo_neon_vent_lenovo_legion/device.py`
- `src/tray/controllers/secondary_static_scene.py`
- `scripts/debug/ite8258-chassis-zone-test.py`

### Tests

- `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py`
- `tests/tray/controllers/core/test_secondary_static_scene_unit.py`
- `tests/tray/pollers/config/core/test_secondary_config_polling_unit.py`

### Docs / changelog

- `CHANGELOG.md` (Unreleased)
- `docs/B-backend-audits/06-ite8258-chassis.md`
- `docs/I-implementation-plans/secondary-lighting-profile-editor-and-simulation-plan.md`

## 4. Dual-seam diagnosis (validated)

Two independent seams combined into the flash-then-dark failure:

### Seam A — Config mirror treated as authoritative too early

**Location:** `src/tray/controllers/secondary_static_scene.py` → `payload_from_config`

**Failure mode:**

- Default / upgraded configs often have `secondary_device_state: {}` or a
  **partial** v0.28.x map (only routes the user touched).
- v0.29.1 treated any mapping as an authoritative profile scene.
- After a successful keyboard write, static secondary reconcile applied missing
  routes as **off** (`turn_off()`).

**Fix:**

- Treat the mirror as authoritative only when:
  1. it is non-empty,
  2. it contains **every** known `supports_profile_state` route, and
  3. each of those entries is a mapping with an explicit `enabled` field.
- Otherwise return `None` and let legacy per-route accessors / defaults complete
  the scene.

### Seam B — Independent virtual-zone `SAVE_PROFILE` on a shared group namespace

**Location:** keyboard + zone devices under
`ite8258_perkey_chassis_logo_neon_vent_lenovo_legion`

**Failure mode:**

- Keyboard, logo, neon, and vent share **one** hardware profile / group list.
- Each surface previously started its own `SAVE_PROFILE` sequence at group 1.
- A child-only write is not a zone-local patch; it **replaces** the parent
  keyboard scene from the start of the group namespace.
- Sharing only the hidraw transport (per-report lock) was insufficient: the
  multi-report profile transaction was still interleaved and incomplete.

**Fix:**

- New `Ite8258ChassisProfileCoordinator`:
  - retains desired primary groups + per-zone groups (protocol data only),
  - serializes every production write as a full multi-report transaction under
    one `RLock`,
  - stages zone-first updates until a primary keyboard scene exists,
  - latches global off so child cleanup cannot replay / relight the scene.

## 5. What looks solid

1. **Coordinator layering** — protocol-only retained scene; no transport ownership;
   fresh proxies can still replay desired state after transport close/reopen.
2. **Full-scene commits** — switch profile → direct mode off → all save-profile
   packets → optional brightness under one lock.
3. **Global-off latch** — `turn_off_all` sets `_globally_off`; subsequent zone
   `turn_off` while latched is no-op on the wire (cleanup path).
4. **Zone brightness footgun removed** — positive `Ite8258ChassisZoneDevice.set_brightness`
   raises; zones share controller brightness with the primary keyboard. Aligns
   with `BRIGHTNESS_POLICY_PRIMARY_SHARED`.
5. **Secondary global off** — `turn_off_secondary_profile_areas` no longer
   narrows by payload; correct for forced-off / suspend on composite hardware.
6. **Unit coverage** targets real contracts:
   - sibling group preservation on zone update / off
   - global-off blocks child replay; resume restores retained scene
   - zone-first staging until keyboard profile exists
   - concurrent non-interleave of multi-report transactions
   - empty / partial config mirrors → legacy (`None`)
   - complete mirror with `enabled` bits → authoritative payload
7. **Docs honesty** — audit and implementation plan explicitly state hardware
   revalidation is still pending.

## 6. Local validation performed

Command:

```bash
.venv/bin/python -m pytest \
  tests/core/backends/ite/test_ite8258_chassis_backend_unit.py \
  tests/tray/controllers/core/test_secondary_static_scene_unit.py \
  tests/tray/pollers/config/core/test_secondary_config_polling_unit.py \
  -q --tb=short
```

Result: **58 passed** (2026-07-15).

Parent-side merged validation remains authoritative if additional tray/profile
suites exist outside this focused set.

## 7. Residual risks and overlooked elements

These are **not merge blockers** for the dual-seam fix, but they are real and
should stay on the radar.

### 7.1 Hardware still unproven (highest residual)

All validation for this follow-up is unit/mock. The 83F5 reporter still needs to
confirm:

- [ ] Mode / effect switches no longer flash then black out
- [ ] Logo / neon / vent survive subsequent keyboard updates
- [ ] Static secondary output works without wiping the keyboard
- [ ] Suspend / resume / forced-off remain clean
- [ ] Brightness changes on keyboard still drive shared controller brightness

**Gate for issue closure:** reporter checklist above, not local green alone.

### 7.2 Desired-scene vs global-off asymmetry

| Call while `_globally_off` | Mutates retained scene? | Writes wire? |
|---|---|---|
| `apply_zone` (positive colour) | **Yes** | No |
| `turn_off_zone` | **No** (cleanup) | No |

If the UI or profile apply path stages zone colours while power-forced off,
resume may restore zones the user thought were off (or the reverse depending on
call order). Likely rare; watch for power + secondary restore bugs.

### 7.3 Process-wide singleton coordinator

Same process-global pattern as `SharedHidrawTransportManager`. Fine for one
controller. Risks:

- Tests that only null `_transport_manager` get a fresh coordinator (current
  tests do this correctly in the paths that matter).
- A second product using the same package without a product-variant registry
  would incorrectly share retained scene state.

The backend audit already tracks product-variant registry as a low-priority
follow-up.

### 7.4 Zone local state optimistic when staged

`Ite8258ChassisZoneDevice.set_color` updates `_is_off` / `_current_brightness`
even when `apply_zone` returns `False` (no primary scene yet → no wire write).

Local device state can disagree with hardware until a keyboard write commits
the combined scene. Only matters for callers that trust `is_off()` / brightness
before primary apply.

### 7.5 Strict authoritative-scene gate (good, with a product edge)

`payload_from_config` requires **every** current `supports_profile_state` route
to be present with `enabled`.

When a **new** secondary route is added later:

- previously “complete” mirrors become incomplete,
- system falls back to legacy interpretation until profiles/config are
  rewritten.

This is safer than false authority, but must be documented in release notes when
new profile-capable routes ship.

### 7.6 `set_primary_brightness` after global off

- Off latched **and** primary groups exist → brightness restore **replays full
  scene** (good).
- Off latched **without** primary groups yet → switch + brightness only (cold
  start edge).

### 7.7 Integration coverage gap

This diff adds strong unit tests but not a full tray end-to-end test of:

> change mode under default empty `secondary_device_state` on composite backend

Pieces are covered; a parent merge suite / future integration test would close
the last automated gap.

### 7.8 Debug script still has broad `except Exception` on close

`scripts/debug/ite8258-chassis-zone-test.py` still uses best-effort
`except Exception` on device close. Acceptable for a manual debug script; do not
copy that pattern into production paths. Not introduced as a new production
silent catch.

## 8. Architectural and organisational notes

### 8.1 What this patch does well

- Separates **transaction coordination** from device wrappers — correct layer for
  composite HID profiles.
- Fixes **both** tray semantics and backend transaction model. Either alone would
  leave intermittent darkness.
- Avoids opportunistic public-API renames; preserves tested device method surface
  while changing internal commit behaviour.

### 8.2 Structural debt (pre-existing, amplified by #7)

#### A. Two different `payload_from_config` helpers

| Helper | Role |
|---|---|
| `secondary_static_scene.payload_from_config` | “Is the config mirror authoritative?” |
| `secondary_lighting_state.payload_from_config` | “Build a non-persistent legacy snapshot” |

Same name, different contracts — easy to misuse in future call sites.

**Suggestion:** rename for clarity, e.g.:

- `authoritative_payload_from_config`
- `legacy_snapshot_from_config`

#### B. Virtual zones modelled as independent devices on a shared profile

Tray still thinks: per-route acquire → `set_color` / `turn_off`.

Hardware needs: patch retained scene → full commit.

The coordinator is a good adapter. Longer term, a single composite surface API
(or an explicit parent transaction owned by tray) would reduce order sensitivity
(keyboard first, then zones).

#### C. “Explicit empty = off” vs “default empty = legacy”

v0.29.x correctly distinguishes:

- **Materialized** mirrors (all routes + `enabled`) → authoritative scene
- **Default / partial** mirrors → compatibility / legacy fallback

This is subtle for support and for future contributors. Call it out in secondary
lighting docs and release notes.

#### D. Issue #7 as a long-lived megathread

Permissions, matrix, secondaries, then 0.29.1 regression all live in one issue.

**Suggestion:** keep this folder’s session docs, and either:

- open a dedicated short regression issue for flash-then-off, or
- maintain a checklist in `issue-7.md` so “fixed on main” is not lost in
  hardware-support noise.

### 8.3 Explicit non-goals of this review

- No requirement to redesign secondary route architecture before landing the fix.
- No claim that all historical #7 software-effect quality notes are resolved.
- No claim of hardware-verified promotion of the experimental backend.

## 9. Recommended reporter hardware checklist

Ship a build (or ask the reporter to test the unreleased branch) with:

1. Fresh full install if udev changed (not required solely for this dual-seam
   code path, but good practice for this device class).
2. Enable experimental backends.
3. Exercise:
   - static keyboard colour
   - hardware effects
   - software effects (keyboard-only and “all compatible devices”)
   - mode / effect switches rapidly
   - logo / neon / vent on and off independently, then change keyboard mode
   - brightness up/down
   - suspend / resume, lid close/open if enabled
4. Confirm: no flash-then-all-dark after mode changes.
5. Attach support bundle + short note if anything still fails.

## 10. Recommended follow-ups (priority order)

| Priority | Item | Owner suggestion |
|---|---|---|
| **P0** | Reporter hardware revalidation of dual-seam fix | Maintainer + reporter |
| **P1** | Optional tray integration test: mode change + empty `secondary_device_state` | Tests |
| **P2** | Rename dual `payload_from_config` helpers | Small cleanup PR |
| **P2** | Document authoritative vs legacy mirror rules near secondary lighting docs | Docs |
| **P3** | Product-variant registry if another `0xc197`-class layout appears | Backend |
| **P3** | Consider composite transaction API vs independent zone devices | Architecture |
| **P3** | Shared hidraw usage/report-descriptor filtering (existing audit item) | Backend |

## 11. Bottom line for maintainers

Land the dual-seam fix after normal parent validation. Tag a build for the
issue #7 reporter with the checklist in §9.

Until hardware confirmation:

- treat this as a **high-confidence regression fix**,
- **not** as hardware-verified closure of issue #7,
- keep residual risks in §7 visible when triaging any post-fix “still dark”
  reports.
