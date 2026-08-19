# Debt Campaign Tracker (2026-08-18)

## Purpose

Post-v0.32.1 consolidated debt backlog. Carries forward the still-open items
from `docs/I-implementation-plans/2026-07-15/maintainability-debt-paydown-plan.md`
(D8, D12, D14, D15) and adds the 2026-08-18 architecture review findings plus
release-process leftovers from the v0.32.1 publish. This doc is the "what to do
next" index; historical detail stays under `docs/Z-legacy/tech-debt/` and older
dated plans.

## Conventions

- Priority: `P0` blocks safe iteration, `P1` high leverage, `P2` phased.
- Effort: `S` / `M` / `L`.
- Status: `todo` | `active` | `monitoring` | `deferred` | `done`.
- Every campaign step must keep `.venv/bin/python -m buildpython --profile=release` green.

## Campaign inventory

| ID | Campaign | Priority | Effort | Status |
|---:|---|:---:|:---:|---|
| C1 | Package identity: rename import root `src` → `keyrgb` | P1 | L | done |
| C2 | Typing parity for the Tk GUI layer | P1 | M | todo |
| C3 | Indirection tax containment (lazy imports, compat facades) | P2 | M | monitoring |
| C4 | Onboarding map upkeep (498 files, `_private` nesting) | P2 | S | monitoring |
| C5 | Release infrastructure (Node 20 action deprecation, local ShellCheck) | P1 | S | monitoring |
| C6 | Hygiene budget paydown (defensive_conversion / hasattr_coupling / cleanup_hotspot) | P2 | S | todo |

---

## C1 — Package identity: `src` → `keyrgb`

**Why the current state is a problem.** The standard, recommended practice is a
`src/` *directory* (src-layout) whose contents are a package named after the
project — `src/keyrgb/…`, installed as `keyrgb`. keyRGB instead makes `src`
itself the importable top-level package: entry points are
`src.tray.entrypoint:main`, imports read `from src.core…`, the app runs as
`python -m src.tray`, and site-packages contains a directory literally named
`src/`.

Consequences:

- **Zero namespacing in site-packages.** Any other project making the same
  choice collides; pip will overwrite/merge a `src/` package without warning.
- **`import src` is ambiguous.** Other checkouts and tools routinely have a
  `src/` directory; resolution depends on cwd / `sys.path` order (this is why
  the repo `./keyrgb` launcher works: repo root lands on `sys.path`).
- **Tooling assumes package name == project identity.** isort/ruff/mypy/
  coverage all need explicit config to treat `src` as first-party.
- **dist↔import mismatch.** The distribution is `keyrgb` but owns a package
  called `src`; uninstall/ghost-file hygiene relies on that link being exact.

Why it works today: AppImage-first distribution (self-contained), dedicated
venvs, and repo-root execution. Pain materializes in shared environments or any
future PyPI-style distribution.

**Scope.** ~498 source files / ~76k LOC of `from src…` imports, tests,
`pyproject.toml` packaging + entry points, AppImage build, buildpython steps
that special-case `src`, docs.

**Options.**
(a) Flat rename: `src/` → `keyrgb/` (minimal churn; not src-layout).
(b) True src-layout: move to `src/keyrgb/` (canonical; double churn).

Recommendation: (a) in one mechanical commit; no compat shim — a `src`
re-export shim would be exactly the facade debt C3 tracks. Cut at a minor
boundary (0.33.0).

**Done 2026-08-18** (unreleased, targets 0.33.0): flat rename executed — `src/`
→ `keyrgb/`, dev launcher `keyrgb` → `keyrgb.sh`, all imports/entry points/
packaging/AppImage/CI/buildpython references rewritten, living docs swept
(dated plans and postmortems keep historical paths), release gate green.
Follow-up: verify the next AppImage install end-to-end via the curl flow.

**Acceptance.** Entry points read `keyrgb.tray.entrypoint:main` etc.;
`pip show -f keyrgb` owns only `keyrgb/`; release profile green; AppImage smoke
green; curl-install flow re-verified.

## C2 — Typing parity for the GUI layer

`keyrgb/gui/**` is now on the same mypy gate as core/tray (follow-imports=normal).
The incremental skip-mode ratchet is closed. Remaining GUI typing debt is local
(`# type: ignore` on a few Tk/protocol facade call sites), not an exclusion:

1. Opt in the smallest leaf modules first (e.g. `gui/windows/uniform.py`,
   `gui/theme/`), fix to zero errors, add to the mypy include set.
2. Ratchet: no module leaves the include set once added.
3. Exit: exclusion removed; GUI covered by the same mypy gate as core/tray.

**Progress (2026-08-19, batch 1).** The opt-in tuple
(`_GUI_PURE_MYPY_TARGETS` in `buildpython/steps/step_type_check.py`) grew from
8 to 109 modules — every `keyrgb/gui/**` module that passes mypy
(`--follow-imports=skip`) in the *combined* run with zero code changes. Note
the combined run is stricter than per-file runs: cross-references between
listed roots resolve to real types, so modules that pass individually can fail
in combination (12 did). Backlog: 50 modules need real annotation work —
38 fail individually, plus those 12 combination failures.

**Progress (2026-08-19, batch 2).** All 12 combination-failure modules fixed
with honest typing (zero `type: ignore`) and added to the tuple, now at 121
modules:

- `_wrap_sync._WrapLabel.configure` narrowed to the one real call shape
  (`configure(*, wraplength: int) -> object`) — satisfies both `tk.Label` and
  `ttk.Label` stubs without `Any`.
- `_settings_scheduler._SchedulerValuesProtocol` members became read-only
  properties with precise types, matching the frozen `SettingsValues`
  dataclass.
- `_DialogContainer` gained the existing `_GridWidget` protocol base.
- per-key `editor_support/actions.py` editor params narrowed from `object` to
  the six real editor protocols (TYPE_CHECKING imports); dropdown `set_value`
  lambdas rewritten to return `None`; `_PerKeyCanvasEditorProtocol`-style
  narrowing for profile config; a typed adapter for the sample-tool release
  callback default.
- `perkey/canvas.py` + `canvas_impl` mixins: Tk-shadow protocol attributes
  replaced by a check-time-only base (`tk.Canvas if TYPE_CHECKING else
  object`), so mixins use real tkinter stub signatures with zero runtime
  change; `_CanvasPointEvent` members became read-only properties (fixes
  `bind` contravariance); `KeyboardCanvas.editor` redeclared with the
  concrete `PerKeyEditor` type to resolve the mixin protocol conflict.

Backlog: 38 modules still fail mypy individually (next batches).

**Progress (2026-08-19, batch 3 — C2 exit for skip-mode).** All 159
`keyrgb/gui/**` modules now pass `mypy --follow-imports=skip` in one combined
run and are listed in `_GUI_PURE_MYPY_TARGETS`. The GUI layer is gated the
same way as the existing 8-module baseline, just complete. Remaining
follow-up (not required to close C2's incremental ratchet): drop
`--follow-imports=skip` and fold `keyrgb/gui` into the primary mypy invocation
so cross-package imports use real types instead of Any. That is a separate,
stricter campaign.

**Progress (2026-08-19 — C2 full exit).** Folded `keyrgb/gui` into the
primary mypy invocation and deleted the skip-mode tuple. Ten follow-imports
errors were real signature mismatches (protocol covariance, `Mapping` key
invariance, `Config` property/setter shape). `support.py` still has
targeted `# type: ignore[arg-type]` on facade call sites; those remain
required even with follow-imports=normal.

Notable batch-3 techniques:
- Declare dynamically-initialized attributes on `PerKeyEditor` /
  `ReactiveColorGUI` so they satisfy the editor/window protocols.
- Protocol data members as `@property` for covariance (Tk `BooleanVar` /
  `StringVar` vs local variable protocols).
- Check-time-only mixin bases and targeted `cast()` at Tk-overload /
  module-vs-Protocol boundaries. `support.py` keeps a small set of
  `# type: ignore[arg-type]` on facade call sites where many local
  protocols meet real Tk modules.
- Reverted a TYPE_CHECKING-only base class on `SupportToolsGUI` (would
  have been a runtime `NameError`).

## C3 — Indirection tax containment

Function-level imports and `__getattr__` compat facades are deliberate (import
cost + cycle avoidance) and policed by the import-scan step and
`tests/test_maintainability_compat_facades_unit.py`. Guardrails:

- No new facade/lazy shim without a maintainability-test entry.
- When a facade's last legacy caller disappears, delete it in the same change.
- Periodic audit: facades that no test asserts are candidates for removal.

## C4 — Onboarding map upkeep

498 files with heavy `_private` subpackage nesting; the map is
`docs/1-src/*`. Rule: any new `_private` subpackage or ownership change updates
the relevant `1-src` doc in the same commit. No other action — the
small-files/single-owner discipline stays.

## C5 — Release infrastructure

- **Node.js 20 deprecation (done 2026-08-18).** Bumped `actions/checkout` to
  v5.0.1 (`93cb6efe…`) and `actions/setup-python` to v6.3.0 (`ece7cb06…`) in
  `ci.yml`/`release.yml`; both are Node 24-native. `softprops/action-gh-release`
  stays at v2.6.2 (`3bb12739…`) — already the latest release; it still declares
  `node20` upstream, so one deprecation annotation will remain until upstream
  cuts a Node 24 release. Re-check upstream before 0.33.0.
  Keep the pin-to-SHA policy (see `.github/workflows/release.yml` comments).
- **Local ShellCheck gap.** `buildpython --profile=release` skips ShellCheck
  when not installed locally; CI covers it. Add a dev-env note (or install
  instruction) to `docs/3-contributing/01-build_runner.md`.

## C6 — Hygiene budget paydown

Budgets only shrink; restore headroom on the at/near-threshold categories seen
in the v0.32.1 release gate:

| Category | Active / budget | Item | Action |
|---|---|---|---|
| defensive_conversion | 1 / 1 | `src/core/effects/reactive/render.py:290` nested `float(float(…))` | Flatten the conversion; restores headroom |
| hasattr_coupling | 1 / 3 | `src/core/effects/reactive/_render_brightness_support.py:109` `setattr` on private attr | Typed state object next time the render state is touched |
| cleanup_hotspot | 6 / 6 | `legacy_snapshot_from_config` family (old D15) | Intentional v0.28→v0.29 profile-migration compat for issue #7 installs; keep until the migration window closes, then remove and reclaim the budget |

## Accepted with exception (not campaigns)

- `src/core/backends/ite8258_perkey_chassis/protocol.py` (710 lines) carries
  `@quality-exception file-size-analysis` — device-local packet builders + LED
  matrix tables. Revisit only if real logic accretes beyond protocol data.
- **v0.32.1 deferred menu rebuild on power-mode applies.** Automatic AC/DC mode
  applies now request one coalesced, post-transition menu rebuild. Residual
  risk: rebuilding while the SNI menu is open can still crash plasmashell
  (v0.25.5 / v0.32.0 history). Monitor field reports; if it recurs, gate the
  rebuild (delay-after-settle) and file under `D-bug-reports`.

## Phase plan

1. **Phase 1 (next):** C1 package rename + C5 actions bump (independent, land
   separately).
2. **Phase 2:** C2 first mypy opt-in batch; C6 quick wins.
3. **Continuous:** C3/C4 guardrails; budget rule enforcement via release gate.

## Cross-references

- Supersedes the "what next" narrative of
  `docs/I-implementation-plans/2026-07-15/maintainability-debt-paydown-plan.md`
  (D8 promoted to C1; D12/D14 folded into C6/accepted-exceptions; D15 → C6).
- Architecture map: `docs/1-src/`.
- Release procedure: `docs/3-contributing/03-release_procedure.md`.
