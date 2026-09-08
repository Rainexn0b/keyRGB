# Architecture enforcement audit — 2026-09-08

Status: implementation complete; validation results recorded below.

## App and build model

KeyRGB separates backend/device transport, core effects and policy, tray runtime
coordination, and standalone Tk tools. Low-frequency sleep/wake intents go
through `keyrgb/tray/deck_pipeline.py`; effect frames stay in their render loops.
Both use the engine's reentrant `kb_lock` at primary-device output boundaries.
Backend transport locks and standalone GUI process ownership are separate
contracts, not substitutes for the engine lock.

`buildpython` is a validation runner as well as a packaging entry point.
Architecture Validation is Step 17, registered in every named profile (`quick`,
`ci`, `debt`, `full`, `release`). GitHub CI runs `ci`; release automation runs
`release`. The gate reads `buildpython/config/architecture_rules.json` and emits
`buildlog/keyrgb/architecture-validation.{json,csv,md}`. Both warning and error
findings fail it. No new tool dependency or additional CI step was necessary.

## Existing enforcement

The baseline had 24 configured rules and passed with no findings. The important
contracts were already present; duplicating them would add maintenance without
additional protection.

| Area | Existing enforcement |
|---|---|
| Primary output | Approved write-owner files plus lexical `kb_lock` around six lighting mutators |
| Concurrency | `_start_lock` → `kb_lock` → `_brightness_fade_lock`; no configured blocking operations under the keyboard lock |
| Observation vs policy | Hardware observers cannot assign desired brightness/effect or forced-off flags; poller engine mutations belong to approved commit leaves |
| Device routing | Secondary/auxiliary modules cannot mutate the primary keyboard through configured tray-engine receivers |
| Layering | Core independent of tray/GUI; GUI independent of tray runtime; backend selection/storage isolated from UI |
| Runtime contracts | Readonly diagnostics config, backend-local composite coordination, explicit reactive dependencies and hardware builder metadata |
| UI safety | Tk async coordinator owns GUI workers; tray renders snapshots; automatic power paths cannot rebuild live menus |

## Changes and evidence

| Gap | Implemented protection | Status |
|---|---|---|
| Relative imports were ignored; several layer rules used line regexes | Resolve `ImportFrom.level` from each repo-relative source path, including `__init__.py`. Convert five import-boundary rules to AST imports. Detect parent imports, comma-separated imports, aliases, and inline imports; ignore documentation strings. | Done |
| `Thread(target=...)` regex missed aliases and argument ordering | AST calls enforce `threading.Thread` and `threading.Timer` ownership outside `tk_async.py`, including imported aliases and simple local constructor aliases. | Done |
| Local keyboard/method aliases and literal `getattr` hid hardware writes | Call scanning follows simple name assignments, annotated assignments, named expressions, bound methods, and literal `getattr` chains. Ownership and lexical locks apply at invocation. Parameters and explicit rebinding shadow aliases. | Done |
| Generator bodies inherited a lock held only when the generator was created | Deferred generator bodies start with an empty lock stack, like function/lambda bodies. The outer iterable still executes in the creation context. | Done |
| `PurePath.match` did not give exclusions recursive `**` semantics | Repo-relative matching handles zero or more directory levels for exclusions and call-owner globs; sibling prefixes do not become implicit matches. | Done |
| Unreadable/invalid source was silently skipped | Read each matched source once per scan, reject read/UTF-8/parse failures with the file path, and return a failing step result. | Done |
| Empty/malformed rule lists, duplicate IDs, key typos, and empty rule corpora could disable enforcement | Validate root/rule/corpus/call structure and relevant string lists; reject unknown rule/corpus/call fields. Production Step 17 rejects rules matching no files after exclusions. | Done |

The strengthened write scanner found existing indirect writes in
`perkey_animation.py` and config polling's `helpers.py`. Their production callers
already held `kb_lock`; this was an implicit caller contract, not evidence of an
observed hardware race. The recovery-save helper now takes and acquires the
keyboard lock itself. Config polling's user-mode helper moved to the already
approved `_apply_callbacks.py` owner and locks both the normal write and the
legacy no-`save` fallback. Reentrant locking preserves the encompassing frame
transaction and write order. The write-owner allowlist was not expanded.

The same scanner now recognizes the existing locked
`getattr(self.kb, "set_color")` brightness-flatten path and the hidden-restore
row/brightness method aliases.

`enable_user_mode_once()` also keeps its bound method and locked invocation in
one closure, so removing its lock is visible to the scanner instead of hidden
behind a generic callback parameter. A readonly backend-policy lookup moved to
the existing `_apply_support.py` module to keep the output owner within the
File Size gate.

## Scope and remaining limits

This remains a syntactic regression gate, not a whole-program concurrency proof.
Simple aliases are tracked in traversal order, not with control-flow joins or
Python's complete scope analysis. Arbitrary object aliases, computed `getattr`
names, `cast`/container indirection, callback forwarding, dynamic imports,
wildcard re-exports, and methods passed into another function are not generally
resolved. Import ownership does not prove that every possible UI dispatch path
uses the coordinator.

Lock checks recognize configured dotted spellings and lexical context managers;
they do not infer lock identity through local aliases, manual acquire/release,
or caller-held locks. Prefer an explicit lock at the output leaf. A deferred
generator write is conservatively rejected even if a particular caller consumes
it immediately under a lock.

Corpus integrity checks the effective set for each rule, not every include glob
individually. The payload checks cover the documented entry points above; they
are not a complete JSON Schema for every legacy nested-rule spelling. The low-level
`scan_architecture()` API still permits partial corpora for focused fixture tests;
the production runner performs the nonempty-corpus check.

Runtime tests remain necessary for FIFO/revision semantics, stale-frame/fade
generation cancellation, forced-off precedence, full composite report
transactions, persistence atomicity, and process-level GUI ownership. Those are
better verified behaviorally than by adding token-pattern rules. Backend/GUI
exclusions from the primary-engine rule remain intentional. No blanket ban on
all `set_color`, all locks, or all platform I/O was added.

## Validation

- Focused architecture and affected effects/config-poller tests: **325 passed**.
- Full CI profile: **18/18 steps passed**, **4,073 tests passed, 1 skipped**.
- Final Architecture Validation: **24 rules, 610 files, 0 findings**.
- `git diff --check`: passed.

Reproduce:

```bash
.venv/bin/python -m pytest -q -o addopts= \
  tests/buildpython/test_buildpython_architecture* \
  tests/buildpython/test_architecture* \
  tests/core/effects/rendering/test_effects_perkey_animation_unit.py \
  tests/tray/pollers/config/
.venv/bin/python -m buildpython --run-steps=17
.venv/bin/python -m buildpython --profile=ci
git diff --check
```

Numeric selectors and quoted display names such as `--run-steps="Architecture Validation"`
are supported after the [CLI output audit](05-CLI-output-audit-2026-09-08.md).
