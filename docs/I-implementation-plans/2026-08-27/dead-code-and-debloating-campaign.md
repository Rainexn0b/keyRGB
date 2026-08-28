# Dead-Code and Debloating Campaign (2026-08-27)

## Purpose

Bounded dead-code removal and footprint de-bloating for the `keyrgb` package
and its build/release tooling. This campaign is strictly **non-feature** work:

- Remove code that is genuinely unused (zero callers in runtime paths, or
  artifacts that should never have shipped).
- Reduce incidental footprint (backup artifacts, loose demo files, loose
  glob packaging, oversized docs assets) where the removal is low-risk.
- **No feature removal.** Nothing user-visible changes behavior.
- **No public entrypoint changes.** `pyproject.toml` entry points, backend
  discovery, and tested public facades are preserved (see Guardrails).

The campaign is intentionally conservative. Every candidate is verified by
both an automated scan *and* manual exact-caller analysis before removal. The
automated scan alone is insufficient: Vulture 2.16 in this repo flags many
Protocol/callback parameters and deliberate `if False` typing blocks that are
not dead code under the project's current policy.

## Explicit correction: `buildpython` is in scope only as a gate, never as a target

`buildpython` is **intentional, first-class product infrastructure** for LLM- and
CI-facing build orchestration. It is **OUT OF SCOPE** for removal, replacement,
or "debloating." Its steps exist as authoritative campaign gates:

- **Step 17 — Architecture Validation**: enforces configured corpus-pattern
  architecture boundaries; any deletion that touches module ownership must keep
  this green.
- **Step 19 — Exception Transparency**: tracks broad-exception debt and
  silent-failure hotspots; deletions must not introduce new broad `except`
  blocks (see Guardrails).
- **Step 20 — Dead Code**: the authoritative campaign gate. `buildpython`
  Step 20 fails the build on unused functions/classes/imports in runtime code
  and is the canonical "did this removal leave the tree clean?" check.

The baseline run for this campaign uses Step 20 as the gate. `buildpython`
itself (and its 20+ steps) is treated as product code, not bloat.

## Conventions

- Priority: `P0` blocks safe iteration, `P1` high leverage, `P2` phased / optional.
- Effort: `S` / `M` / `L`.
- Status: `todo` | `active` | `monitoring` | `deferred` | `done`.
- "Zero-caller" means no runtime caller outside tests; confirmation requires
  manual exact-caller analysis, not just Vulture output.
- Every campaign step must keep
  `/tmp/opencode/keyrgb-review-venv/bin/python -m buildpython --run-steps=20`
  green, and the release profile green before campaign close
  (`.venv/bin/python -m buildpython --profile=release`).

## Baseline

**Command (isolated Vulture 2.16 run via the review venv):**

```
/tmp/opencode/keyrgb-review-venv/bin/python -m buildpython --run-steps=20
```

**Result:** 30 findings, **0 actionable** under current policy.

**Why 0 actionable:**

- Twenty-eight findings are unused parameter names in Protocol method
  signatures, callback signatures, Tk-style keyword protocols, or tests. They
  are intentionally informational under Step 20's current policy.
- Two findings are deliberate `if False:` typing blocks in
  `keyrgb/gui/perkey/canvas_impl/_canvas_drawing.py` and `_canvas_events.py`;
  they are check-time imports, not reachable runtime branches.
- The manually identified zero-caller symbols in W3 and test-only runtime
  helpers in W5 were not Step 20 findings. Vulture's whole-corpus name analysis
  can treat test references or same-name methods as usage, so those inventories
  need the separate exact-caller audit recorded below.

**Conclusion:** Vulture is a useful *first-pass signal*, not a verdict.
Manual exact-caller analysis complements it, and that analysis drives the
inventory below. The 30-count baseline is recorded for regression comparison;
it is not expected to fall when a manually identified symbol that Vulture did
not report is removed.

## Guardrails (hard rules for this campaign)

1. **Preserve `pyproject.toml` entry points** (`keyrgb.tray.entrypoint:main`,
   `keyrgb-perkey`, `keyrgb-calibrate`, `keyrgb-diagnostics`, etc.). No entry
   point is removed or renamed in this campaign.
2. **Preserve backend discovery** (`keyrgb/core/backends/*`, the backend
   registry, and sysfs-first / USB-fallback selection). Do not delete or merge
   hardware protocol modules merely to save LOC (see W9).
3. **Preserve tested public facades** and caller expectations. Compat facades
   follow the C3 policy from `docs/I-implementation-plans/2026-08-18/
   debt-campaign-tracker.md` (delete a facade only in the same change that
   removes its last legacy caller; no new shim without a maintainability-test
   entry). See W8.
4. **Keep Linux-first / kernel-backed assumptions.** sysfs/`/sys/class/leds`
   remains preferred over USB fallback where backend selection is involved.
5. **No new broad exception handling.** Removals must not paper over missing
   callers with `except Exception` or silent fallbacks. Do not edit generated
   output in `buildlog/`, `htmlcov/`, or build artifacts.
6. **Full relevant validation** per change: focused `pytest` for touched
   areas, `ruff`, and the applicable `buildpython` steps (17/19/20). Release
   profile green before campaign close.
7. **No ITE USB-ID additions** without hardware evidence, diagnostics, and
   tests (standing repo rule).

## Campaign inventory

| ID | Workstream | Priority | Effort | Status |
|---:|---|:---:|:---:|---|
| W1 | Broken `keyrgb-tuxedo` launcher + its 3 `buildpython` references | P1 | S | done (Phase 1) |
| W2 | Tracked `.orig` backup + missing `*.orig` ignore | P1 | S | done (Phase 1) |
| W3 | Zero-caller symbols (runtime) | P1 | M | done (Phase 1) |
| W4 | Color-wheel demo move/remove | P2 | S | done (Phase 1) |
| W5 | Test-only runtime helpers (API-review-required tranche) | P2 | M | done (post-Phase 1) |
| W6 | `requirements.txt` vs `pyproject` dependency source-of-truth | P1 | M | done (post-Phase 1) |
| W7 | `evdev`/`pywayland` optional-extra idea | P2 | S | rejected (keep required) |
| W8 | Compatibility facade audit (tied to C3) | P2 | M | done (post-Phase 1) |
| W9 | `scale_color_for_brightness` pure-math duplication candidate | P2 | S | done (narrow hoist only) |
| W10 | `package-data` glob tightening + docs/assets optimization | P2 | S | deferred (optional) |

---

## W1 — Broken `keyrgb-tuxedo` launcher and its `buildpython` references

**Problem.** `keyrgb-tuxedo` (repo root) is a Bash launcher that `exec`s
`keyrgb-tuxedo-gui.py`, a file that **does not exist** anywhere in the tree
(confirmed: no `keyrgb-tuxedo-gui.py` present). The launcher is dead and
broken — it can never succeed.

**Evidence.**
- `keyrgb-tuxedo:14` → `exec "$PYTHON" keyrgb-tuxedo-gui.py "$@"` (target absent).
- The launcher is also referenced by `buildpython` in three places, which now
  scan/treat a non-existent GUI target:
  - `buildpython/steps/step_import_scan.py:74` → `[root / "keyrgb", root / "keyrgb-tuxedo"]`
  - `buildpython/steps/file_size_analysis/usage_graph.py:8` → `_TOP_LEVEL_ROOT_FILES = ("keyrgb.sh", "keyrgb-tuxedo")`
  - `buildpython/steps/code_markers/scanning.py:27` → `[root / "keyrgb", root / "keyrgb-tuxedo"]`

**Risk.** Low. Removing the launcher and its three references cannot affect
any runtime path (the launcher has no callers and targets a missing file).
**However,** `buildpython` is product infrastructure (see Explicit correction):
the three references must be *corrected*, not used as a pretext to debloat
`buildpython`. The fix is to drop the `keyrgb-tuxedo` literal from those three
  scans (its target is absent from the current tree), leaving the rest of each step
untouched.

**Status.** `done` — removed in Phase 1. The now-empty top-level-file loops
in the import and code-marker scanners were removed with the stale literal;
package scanning remains owned by each scanner's existing recursive root.

**Acceptance.**
- `keyrgb-tuxedo` removed from the repo root.
- The three `buildpython` scan literals no longer reference `keyrgb-tuxedo`.
- Step 09 (Import Scan), Step 05 (Code Markers), and Step 06 (File Size) still
  pass; Step 20 green.

**Migration order.** (1) Remove the root `keyrgb-tuxedo` file. (2) Edit the
three `buildpython` lines to drop `"keyrgb-tuxedo"`. (3) Re-run steps 05/06/09
and step 20.

---

## W2 — Tracked `.orig` backup and missing `*.orig` ignore

**Problem.** A `.orig` backup file is tracked in the repository, and there is
no `*.orig` entry in `.gitignore`. This is incidental footprint/leakage, not
feature code.

**Evidence.** The tracked file is
`tests/core/effects/reactive/core/test_reactive_memory_buffers_unit.py.orig`;
its imports still use the removed `src.*` package root, and
`docs/O-optimisations/reactive-typing-smoothness-upgrades.md:277-279` already
records it as a likely merge/rebase leftover. `.gitignore` lacks a `*.orig`
rule, so future merge/patch artifacts could also be tracked.

**Risk.** Low. Safe artifact cleanup.

**Status.** `done` — backup deleted and `*.orig` added to `.gitignore`.

**Acceptance.**
- The tracked `.orig` file is removed (`git rm --cached` + working-tree delete,
  or `git rm` if appropriate) and its content is confirmed to be a stale backup
  with no unique data.
- `.gitignore` gains a `*.orig` ignore rule.
- No other tracked file is affected; `git status` clean of the artifact.

**Migration order.** (1) Confirm the `.orig` is a pure backup (diff against the
real file). (2) `git rm` it. (3) Add `*.orig` to `.gitignore`. (4) Commit
separately.

---

## W3 — Zero-caller symbols (runtime)

**Problem.** A set of runtime symbols have no callers in runtime paths
(confirmed or strongly indicated by Vulture + manual grep). These are the
highest-leverage, genuinely-dead candidates. Each must still pass manual
exact-caller analysis before deletion (Vulture false-positives on Protocol
members and dynamic callbacks are common here).

**Inventory (candidate → evidence).**

| Symbol | Location | Notes |
|---|---|---|
| `ALL_EFFECTS_SET` | `keyrgb/core/effects/catalog.py:57` | `Final[frozenset]` of `ALL_EFFECTS`; check for any reader outside tests. |
| `scaled_color_map` | `keyrgb/core/effects/perkey_animation.py:102` | Nonzero variant `scaled_color_map_nonzero` *is* used (e.g. `fades.py:214`, `_effects_particles.py:114`); confirm the plain variant is unreferenced. |
| `open_matching_ite8910_style_hidraw_transport` | `keyrgb/core/backends/shared_hidraw_probe.py:140` | Shared hidraw probe helper; confirm no caller post-refactor. |
| `_configured_recovery_brightness` | `keyrgb/tray/pollers/hardware/_recovery.py:312` | Tray recovery helper; confirm no remaining caller. |
| `ConfigFastPathTrayProtocol` | `keyrgb/tray/protocols.py:202` | Protocol; confirm no conforming/runtime user. |
| `software_target_callback` | `keyrgb/tray/ui/_menu_callbacks.py:109` | Menu callback factory; confirm no wired caller. |
| `on_color_release` / `on_apply` (uniform interactions) | `keyrgb/gui/windows/_uniform_color_interactions.py:165,193` | Uniform-window callback functions; distinct from the live `_on_color_release`/`_on_apply` methods on uniform GUI state. Confirm zero wiring. |
| Six dead support-window job-wiring helpers | `keyrgb/gui/windows/_support/_support_window_job_wiring.py:20,33,83,105,125,144` (pre-removal lines) | `build_run_debug_job_kwargs`, `build_run_discovery_job_kwargs`, `dispatch_save_support_bundle_job`, `dispatch_open_issue_form_job`, `build_collect_missing_evidence_job_kwargs`, and `build_backend_speed_probe_job_kwargs`; removing the dispatch helpers also made `build_save_support_bundle_job_kwargs` and `build_open_issue_form_job_kwargs` zero-caller, so those dependent helpers were removed in the same slice. The backend-speed-probe builders remain live. |
| Support-job Protocols made obsolete by those dispatch removals | `keyrgb/gui/windows/_support/_support_window_job_wiring.py:7-17` | `_SaveSupportBundleFn`, `_OpenIssueFormFn`, and `_SupportJobsLike` are used only by the two dead dispatch helpers. |
| Uniform-interaction Protocols/helpers made obsolete by callback removal | `keyrgb/gui/windows/_uniform_color_interactions.py:19-29,59-75,78-85` | Remove only members whose final use is `on_color_release` or `on_apply`; retain shared types used by live drag/apply helpers. |

**Risk.** Low-to-medium. Protocol/callback symbols carry the highest
false-positive risk (Vulture cannot see dynamic Tk wiring), so each requires a
manual grep of all `import` and attribute-access sites before removal.

**Status.** `done` — manual exact-caller analysis confirmed the listed symbols
and their dependent helper types had no remaining callers. All were removed;
the live similarly named functions and backend-speed-probe builders remain.

**Acceptance.**
- Each listed symbol is either (a) removed with a proven zero-caller analysis
  recorded in the progress log, or (b) moved to a "rejected / keep" note with
  the reason (e.g. dynamic callback, Protocol satisfied at runtime).
- No public facade or entry point is affected.
- Step 20 green after each removal; focused `pytest` for the owning module
  stays green.

**Migration order.** (1) For each symbol, grep all of `keyrgb/` + `tests/` for
the name. (2) If zero runtime callers, delete in a small, isolated commit.
(3) Re-run step 20 + focused pytest. (4) Record the resolution in the progress
log.

---

## W4 — Color-wheel demo move/remove

**Problem.** A color-wheel demo (interactive sample/visualization used in the
per-key editor area) is shipped as loose runtime code. It is a demo, not a
feature referenced by any entry point.

**Evidence.** The candidate is
`keyrgb/gui/widgets/color_wheel/demo.py`, a self-contained `main()` guarded by
`if __name__ == "__main__"` with no package entry point or repo import. It is
distinct from the production color-wheel widget and the per-key editor's live
`PerKeyEditor._on_color_release` path.

**Risk.** Low if it is truly unreferenced by any entry point; medium if the
calibrator/editor imports it for a live preview. Exact reachability must be
confirmed.

**Status.** `done` — the demo module and the widget module's demo-only
`__main__` handoff were removed. The production widget and package entrypoints
are unchanged.

**Acceptance.**
- Demo confirmed unreferenced by any entry point and any non-demo module, then
  either removed or relocated under a clearly-marked `demos/` area.
- No change to the production per-key editor color-release path.
- Step 20 + focused `pytest` for `keyrgb/gui/perkey` green.

---

## W5 — Test-only runtime helpers (API-review-required tranche)

**Problem.** A set of helpers were defined in production modules but existed
only to support the test corpus. They were identified by manual exact-caller
analysis rather than Step 20. They were not automatic deletions: their
publicness and the value of their test contracts required an API review.

**Inventory (defined in production code, used by tests).**

| Helper | Location |
|---|---|
| `_spec_for_backend` | `keyrgb/core/backends/registry.py:80` |
| `domain_for_key` | `keyrgb/core/config/domains.py:118` |
| `assert_defaults_partitioned` | `keyrgb/core/config/domains.py:137` |
| `brightness_factor` | `keyrgb/core/effects/timing.py:38` |
| `load_per_key_colors_from_config` | `keyrgb/core/effects/perkey_animation.py:52` |
| `safe_optional_int_attr` | `keyrgb/core/utils/safe_attrs.py:157` |
| `ensure_repo_root_on_sys_path_str` | `keyrgb/core/runtime/imports.py:123` |

**API-review decision.** Remove all seven. None was re-exported from a package
`__init__`, named by an entrypoint, documented as a supported API, or called by
production code. `_spec_for_backend` was private; the domain assertion stated
that it existed for tests; the effect helpers were obsolete/redundant; and the
remaining generic utilities were speculative APIs with no caller. The useful
backend-laziness and config-domain partition invariants remain in tests rather
than forcing test-only helpers onto the runtime surface.

Removing `ensure_repo_root_on_sys_path_str` also exposed its entire sys.path
insertion chain as production-dead, so `ensure_repo_root_on_sys_path`,
`ensure_on_sys_path`, and `add_first_existing_to_sys_path` were removed in the
same slice. Live repo-root detection and subprocess-launch functions remain.

**Status.** `done` — completed as a dedicated post-Phase 1 tranche.

**Acceptance.** Met: API decision recorded, useful invariants retained in
tests, dedicated helper-only tests removed, and focused Ruff/pytest plus Steps
17, 19, and 20 green.

---

## W6 — `requirements.txt` vs `pyproject` dependency source-of-truth

**Problem.** The repo carries both `pyproject.toml` (the modern, authoritative
packaging source) and a `requirements.txt`. The AppImage build consumes
`requirements.txt`, so the two can drift. This is a *dependency-source-of-truth*
campaign, not a simple deletion.

**Risk.** High if done naively: the AppImage pipeline depends on
`requirements.txt`. Removing or "debloating" it without redesign breaks the
AppImage build.

**Design decision.** Preserve the existing AppImage layout and source-copy
behavior. A shared `buildpython.utils.project_metadata` reader now parses the
non-empty `[project].dependencies` list with stdlib `tomllib` or the Python 3.10
`tomli` fallback. The AppImage builder passes those specifiers directly to pip
for the existing `site-packages` target. This avoids both a generated manifest
and a riskier move of the `keyrgb` package inside the AppImage.

**Implementation.** `requirements.txt` was deleted; redundant `pip install -r`
steps were removed from development installation and CI/release workflows;
repo validation now requires valid non-empty project dependencies; Python 3.10
dev environments install `tomli` through the `dev` extra; and current usage and
research docs point contributors to `pyproject.toml`. Metadata parsing has one
owner shared by AppImage and repo validation, with narrow parse/read errors and
no broad exception fallback.

**Status.** `done` — completed as a dedicated post-Phase 1 tranche.

**Acceptance.** Met: `pyproject.toml` is the sole runtime dependency manifest,
the installed dependency set and AppImage layout are unchanged, focused parser
and packaging tests pass, repo/import validation is green, and the AppImage
build and smoke test pass.

---

## W7 — `evdev` / `pywayland` optional-extra idea

**Problem.** An idea was floated to make `evdev` / `pywayland` optional
extras. This is a *product decision* (changes install surface and supported
input paths), not a debloating deletion.

**Risk.** Product/UX risk; out of scope for a pure dead-code campaign.

**Decision.** Reject the optional-extra split and keep both dependencies in the
default runtime set. The existing runtime behavior already degrades safely when
Wayland is not in use or an input path is unavailable. Making installation
conditional would add multiple supported package shapes, complicate AppImage /
source-install parity, and allow reactive-input or idle-tracking features to be
silently absent because a user installed the wrong extra. That complexity is
not justified by the modest dependency-footprint reduction.

**Status.** `rejected` — `evdev` and `pywayland` remain in
`[project].dependencies`; no implementation change is planned.

---

## W8 — Compatibility facade audit (tied to C3)

**Problem.** The 2026-08-18 debt tracker defines **C3 — Indirection tax
containment**, which policed `__getattr__` compat facades via the import-scan
step and `tests/test_maintainability_compat_facades_unit.py`. Some facades may
now have zero legacy callers and be retirement candidates.

**Policy (from C3).**
- No new facade/lazy shim without a maintainability-test entry.
- When a facade's last legacy caller disappears, delete it in the same change.
- Periodic audit: facades no test asserts are candidates for removal.

**Risk.** Medium. Public shim deletion is an API decision; deleting a shim
whose last *internal* caller is gone but whose *public* contract is still
implied is premature.

**Audit decision.** Retain the tested/public compatibility facades and explicit
monkeypatch seams, including `_uniform_init_adapter.py`, profile compatibility
exports, reactive render-brightness support, tray lighting helpers, and hardware
recovery facades. Production callers already use their owner modules where
appropriate, but tests and caller contracts still intentionally pin those
surfaces.

Two private, untested one-hop dependency aggregators had only one internal
caller each and no compatibility contract. They were removed:
`_support_window_runtime_deps.py` and `_reactive_color_runtime.py`. Their window
entry modules now bind the same names directly from owner/service modules. The
intentional `_reactive_color_init_adapter.py` remains the architecture boundary
for initialization dependencies and backend selection; state operations now go
directly to `_reactive_color_state.py`.

**Status.** `done` — audit complete, intentional facades retained, and only the
two proven internal pass-through modules removed. No public entrypoint or tested
facade was deleted.

**Acceptance.**
- Audit completed: each facade's internal vs external callers enumerated.
- Internal-only facades removed when their last internal caller is gone (same
  change), with the compat-facade unit test updated.
- Public shims retained unless an explicit API-decision record permits removal.
- Step 09 (Import Scan) and the facade unit test stay green.

---

## W9 — `scale_color_for_brightness` pure-math duplication candidate

**Problem.** `scale_color_for_brightness` is defined identically in two backend
protocol modules:

- `keyrgb/core/backends/ite8297_uniform/protocol.py:26`
- `keyrgb/core/backends/ite8233_none_chassis_lightbar_clevo/protocol.py:132`

Both are used by their respective `device.py` callers
(`ite8297_uniform/device.py:46`, `ite8233_…/device.py:82`), so neither is
currently dead. The *pure-math* body is duplicated and could be hoisted to a
shared helper.

**Scope boundary.** This is a **pure-math duplication** candidate only.
**Broader backend merging is explicitly OUT OF SCOPE** (see Guardrail 2):
hardware protocol modules must not be merged merely to save LOC, and ITE USB-ID
behavior must not change.

**Risk.** Low for the narrow hoist; medium if it tempts a larger backend merge.

**Implementation.** The exact pure-math body now lives in
`keyrgb/core/effects/colors.py`. Both protocol modules re-export that same
function object, preserving their existing module APIs and device callers.
Brightness clamping (`0..50`), channel conversion/clamping, and rounding are
unchanged; no protocol packet, USB ID, or device quirk changed.

**Status.** `done` — narrow shared-math hoist complete; broader backend merging
remains out of scope.

**Acceptance (if ever taken).**
- Pure function hoisted to a shared, backend-neutral math helper with identical
  behavior; both backends call it; per-backend tests green; no protocol/USB-ID
  change.

---

## W10 — `package-data` glob tightening + docs/assets optimization

**Problem.** `package-data` globs may be broader than necessary (shipping
non-essential files into the wheel/AppImage), and docs assets may be
unoptimized (large images, stale binaries).

**Risk.** Low. Footprint-only; must not drop files needed at runtime
(templates, keymaps, udev rules referenced by install paths).

**Status.** `deferred` — low-priority optional. Not part of Phase 1.

**Acceptance.**
- Glob tightened with a test/audit proving every runtime-needed data file is
  still packaged.
- Docs assets optimized without quality loss; no broken doc links.

---

## Phase plan

### Phase 1 (done)

**In scope:**
- **W1** — broken `keyrgb-tuxedo` launcher removal + 3 `buildpython` literal
  corrections.
- **W2** — tracked `.orig` backup removal + `*.orig` gitignore rule.
- **W3** — zero-caller runtime symbols, each gated on manual exact-caller
  analysis (delete only with proven zero callers; record rejected-keep notes
  otherwise).
- **W4** — color-wheel demo move/remove *if* caller analysis confirms it is
  unreferenced by any entry point (safe-artifact class).

**Explicitly NOT part of Phase 1:**
- **W5** test-only runtime helpers (API-review-required tranche).
- **W6** `requirements.txt` vs `pyproject` dependency source-of-truth (design
  first).
- **W7** `evdev`/`pywayland` optional-extra idea (product decision).
- **W8** compatibility facade retirement (public shim deletion only after
  explicit API decision; internal-caller audit first).
- **W9** broader backend merging (out of scope); only a noted pure-math
  candidate.
- **W10** package-data glob tightening + docs/assets optimization (optional).

W1-W4 implementation and focused/full-test validation are complete. The
pre-existing extra blank line in
`tests/tray/controllers/power/test_tray_lighting_controller_power_state_unit.py:450`
was normalized with Ruff Format, after which the full release profile passed
with Health 100/100. Step 20, AppImage build, and AppImage smoke are green;
ShellCheck remains an accepted local skip because the executable is unavailable.

### Later tranches
- W8 and W9 are complete under their acceptance gates.
- W10 remains deferred and optional.

---

## Validation matrix

Run the smallest focused command that can fail on the edited path.

| Change area | Commands |
|---|---|
| Touched runtime module (W3/W4) | `pytest tests/<owning_module>` (focused) |
| Any Python edit | `ruff check keyrgb buildpython tests` |
| Caller-boundary / facade edits (W3/W8) | `python -m buildpython --run-steps=9` (Import Scan) |
| Architecture-boundary edits | `python -m buildpython --run-steps=17` (Architecture Validation) |
| Exception-transparency / runtime-boundary edits | `python -m buildpython --run-steps=19` (Exception Transparency) |
| Every removal | `/tmp/opencode/keyrgb-review-venv/bin/python -m buildpython --run-steps=20` (Dead Code gate) |
| Campaign close | `.venv/bin/python -m buildpython --profile=release` (full release gate green) |

All commands above are run from the repo root. Hardware tests remain opt-in
(`KEYRGB_HW_TESTS=0` for build steps).

---

## Progress log

### 2026-08-27 — Baseline established
- Isolated Vulture 2.16 run via
  `/tmp/opencode/keyrgb-review-venv/bin/python -m buildpython --run-steps=20`:
  **30 findings, 0 actionable** under current policy (28 signature parameters
  and two deliberate `if False` typing blocks; complemented by manual
  exact-caller analysis).
- Campaign tracker created. **No code cleanup has landed yet** — this entry
  records the baseline and the plan only.

### 2026-08-27 — Tracker authored
- `docs/I-implementation-plans/2026-08-27/dead-code-and-debloating-campaign.md`
  created with purpose, buildpython correction, guardrails, W1–W10 inventory,
  Phase 1 definition, validation matrix, and this progress log.
- Added to `docs/I-implementation-plans/README.md` under Active follow-up plans.
- No production code or tests were modified.

### 2026-08-27 — Phase 1 implementation landed in the worktree
- **W1:** removed the broken `keyrgb-tuxedo` launcher, removed its three stale
  scanner references, and deleted the two top-level-file loops that became
  empty while preserving recursive package scanning and `keyrgb.sh` usage-graph
  ownership.
- **W2:** deleted
  `tests/core/effects/reactive/core/test_reactive_memory_buffers_unit.py.orig`
  and added `*.orig` to `.gitignore`.
- **W3:** removed all listed core/tray/GUI zero-caller symbols. Support-window
  cleanup also removed the two kwargs builders that became orphaned when their
  dead dispatch wrappers were removed; live backend-speed-probe wiring remains.
- **W4:** removed `keyrgb/gui/widgets/color_wheel/demo.py` and the demo-only
  `__main__` import from `color_wheel.py`; production color-wheel behavior and
  public entrypoints are unchanged.
- Net implementation cleanup: **483 tracked lines deleted and 7 lines added**
  outside this campaign document (including stale artifacts and README entry).
- Validation: 1,122 focused tests passed; merged Ruff check passed; buildpython
  Steps 5, 6, 9, 17, 19, and 20 passed; full Step 2 passed with 3,621 passed and
  1 skipped; Steps 1, 4, 8, 10, 13, 16, and 18 passed. Step 21 skipped because
  local ShellCheck is unavailable.
- The initial release-profile attempt stopped at Ruff Format on the then-unchanged
  `tests/tray/controllers/power/test_tray_lighting_controller_power_state_unit.py:450`.
  No campaign file was reported unformatted; the follow-up closure is recorded below.

### 2026-08-27 — Phase 1 release gate closed
- Ran Ruff Format on the single pre-existing formatting finding in
  `tests/tray/controllers/power/test_tray_lighting_controller_power_state_unit.py`
  (one excess blank line removed); its focused test file passed with 21 tests.
- `.venv/bin/python -m buildpython --profile=release` passed in 68.5 seconds:
  **17/18 steps passed, Health 100/100**, with 3,621 tests passed and 1 skipped,
  90.23% coverage, Step 20 green, and both AppImage stages green.
- ShellCheck was the only skipped release-profile step because the executable is
  not installed locally. Phase 1 is closed; W6-W10 remain deferred or
  monitoring under their documented decision gates.

### 2026-08-27 — W5 API review and removal
- API review confirmed all seven W5 helpers had zero production callers, no
  package re-export, no entrypoint, and no supported public documentation.
- Removed `_spec_for_backend`, `domain_for_key`,
  `assert_defaults_partitioned`, `brightness_factor`,
  `load_per_key_colors_from_config`, `safe_optional_int_attr`, and
  `ensure_repo_root_on_sys_path_str`; also removed dependent constants/imports
  and the production-dead sys.path insertion chain exposed by the last removal.
- Preserved backend-registration laziness and DEFAULTS/domain partition and
  overlap checks directly in tests. Removed tests that only kept obsolete or
  speculative helpers alive.
- Merged focused validation: **102 tests passed**; Ruff passed; buildpython
  Steps 17, 19, and 20 passed with Health 100/100.
- W5 changed 34 lines of invariant-preserving tests while deleting 274 runtime
  and helper-only test lines, for a net reduction of 240 tracked lines.
- Full release profile passed after W5 in 38.7 seconds: **17/18 steps passed,
  Health 100/100**, 3,608 tests passed and 1 skipped, 90.24% coverage, and both
  AppImage stages green. ShellCheck remained the sole accepted local skip.

### 2026-08-27 — W6 dependency source consolidated
- Chose metadata extraction rather than installing the project into the
  AppImage target, preserving the established `usr/lib/keyrgb/keyrgb` source
  layout and asset paths.
- Added one strict buildpython project-metadata reader shared by AppImage and
  repo validation; Python 3.10 uses the `tomli` dev dependency and newer Python
  uses `tomllib`.
- Deleted `requirements.txt` and removed its redundant dev-install, CI, and
  release-workflow consumers. Updated local-environment and backend-research
  documentation to identify `[project].dependencies` as canonical.
- Focused W6 validation: 20 buildpython tests passed; Ruff, Ruff Format, mypy,
  and `bash -n scripts/install_dev.sh` passed. Buildpython Steps 9, 10, 14, and
  15 passed with Health 100/100.
- Full release profile passed in 38.7 seconds: **17/18 steps passed, Health
  100/100**, 3,619 tests passed and 1 skipped, 90.24% coverage, Step 20 green,
  and AppImage build/smoke green. ShellCheck remained the sole local skip.

### 2026-08-27 — W7 optional dependency split rejected
- Kept `evdev` and `pywayland` as normal runtime dependencies. Runtime fallback
  already handles sessions where Wayland or input tracking is unavailable;
  optional extras would complicate installation and support while making full
  functionality dependent on selecting the correct package variant.
- No code or packaging change was made for W7.

### 2026-08-28 — W8 facade audit and W9 math deduplication
- **W8:** audited GUI/core/tray compatibility surfaces and retained every
  tested/public facade and intentional monkeypatch seam. Deleted only the
  private single-caller `_support_window_runtime_deps.py` and
  `_reactive_color_runtime.py` pass-through modules; preserved all window-level
  aliases and routed reactive backend selection through the intentional init
  adapter to satisfy the architecture boundary.
- **W9:** moved the identical RGB/brightness scaling body to
  `keyrgb/core/effects/colors.py`; both ITE protocol modules re-export the shared
  helper, and focused edge/identity tests pin exact behavior.
- Merged focused validation passed with **158 tests**; Ruff, Ruff Format, mypy,
  buildpython Steps 9, 17, 19, and 20 passed. Step 6 also confirmed W8 introduced
  no import-block, delegation, middle-man, or unreferenced-file regression.
- The full release profile passed in 40.8 seconds: **18/18 steps passed, Health
  100/100**, 3,639 tests passed and 1 skipped, 90.24% coverage, ShellCheck
  green, and AppImage build/smoke green. The import scan's unavailable `gi`
  probe remained informational.

---

## Cross-references

- **C3 — Indirection tax containment** in
  `docs/I-implementation-plans/2026-08-18/debt-campaign-tracker.md`: the
  compatibility-facade audit policy that W8 follows.
- **Lane registry**: `docs/0-governance/lane-registry.md` (`I-implementation-
  plans` = bounded implementation/refactor campaign plans; this doc belongs
  there).
- **Build system**: `docs/1-buildpython/` — `buildpython` Step 20 is the
  authoritative dead-code gate referenced throughout.
- **Release procedure**: `docs/3-contributing/03-release_procedure.md` — the
  release profile that must be green before campaign close.
- **Backend guides**: `docs/B-backend-guides/` — hardware-protocol modules
  protected by Guardrail 2 (no merge-to-save-LOC).
