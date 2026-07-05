# Typed Config And State Models Assessment

## Problem Statement

KeyRGB already uses typed dataclasses and protocols effectively in several subsystems, but the core config path still centers on a mutable `dict[str, Any]` plus string-keyed lookups. That dict carries multiple meanings at once:

- persisted JSON loaded from disk
- defaults merged with persisted values
- normalized runtime settings after coercion
- compatibility aliases and fallback keys
- ad-hoc snapshots for diagnostics, tray polling, and support tooling

That approach is pragmatic and backward-compatible, but it pushes interpretation work outward. Instead of one place defining what a valid config or runtime snapshot looks like, the codebase re-expresses that contract in accessors, coercion helpers, pollers, diagnostics collectors, settings adapters, and tests.

The maintainability issue is not that KeyRGB is "untyped." It is that the untyped zone is still wider than it needs to be for config and runtime-state handling. Moving more of that data into small typed models would narrow ambiguity, reduce repeated fallback logic, and make changes safer without requiring a disruptive rewrite of the on-disk JSON schema.

## Existing Strengths In The Current Approach

The current design has real strengths and should be treated as the base to extend, not something to replace wholesale.

- `src/core/config/defaults.py` gives the project one authoritative default map, with comments explaining semantics and compatibility intent.
- `src/core/config/config.py` already wraps persistence behind a `Config` object instead of exposing raw JSON reads and writes everywhere.
- `src/core/config/file_storage.py` isolates atomic save/load behavior and preserves compatibility with older config values.
- `src/core/config/_lighting/_coercion.py` separates normalization rules from UI code.
- `src/gui/settings/settings_state.py` already uses a typed `SettingsValues` dataclass as a read/apply boundary for settings UI work.
- `src/tray/pollers/config_polling_internal/core.py` already uses a frozen `ConfigApplyState` dataclass for tray config polling.
- `src/core/diagnostics/model.py` already uses a top-level `Diagnostics` dataclass.
- `src/core/power/policies/power_source_loop_policy.py` already models power-loop inputs and outputs with dataclasses instead of passing around loose dicts.
- `src/tray/protocols.py` shows the repo is already comfortable using typed protocols to document runtime contracts.

The practical takeaway is that KeyRGB already contains the migration pattern this note recommends: keep IO boundaries tolerant, but convert internal state into typed value objects once it crosses that boundary.

## Where String-Keyed State Is Costing Clarity

### 1. The Same Concept Exists In Several Shapes

Brightness is not one field with one contract. The current config path distinguishes `brightness`, `perkey_brightness`, `reactive_brightness`, `battery_saver_brightness`, `ac_lighting_brightness`, `battery_lighting_brightness`, `screen_dim_temp_brightness`, and secondary-device brightness entries. That is a reasonable domain model, but the shape is expressed as many unrelated string keys rather than as a typed group of related values.

The same is true for color state: `color`, `reactive_color`, `lightbar_color`, `secondary_device_state[*].color`, and serialized `per_key_colors` all represent lighting state, but they do not share one typed model or one normalization contract.

### 2. Compatibility Logic Is Scattered Instead Of Encoded Once

Several fields have alias or fallback semantics:

- `power_management_enabled` vs `management_enabled`
- `lightbar_*` compatibility keys vs `secondary_device_state["lightbar"]`
- `perkey_brightness` falling back to `brightness`
- `reactive_brightness` falling back to `brightness`
- tray state like `return_effect_after_effect` and `tray_device_context` living beside durable preferences

Each of those rules is reasonable in isolation. The cost comes from needing to remember which caller sees raw state, which caller sees normalized state, and which caller is responsible for checking aliases.

### 3. Presence Matters As Much As Value, But The Model Does Not Express That

`coerce_loaded_settings()` re-opens the config JSON file to check whether `perkey_brightness` was actually present on disk before deciding how to backfill it. That is a strong sign that the runtime mapping does not capture an important distinction: "field absent" vs "field present but invalid/defaulted."

When a system has to peek back at the raw serialized form to recover that distinction, a typed boundary object is usually missing.

### 4. Accessor Contracts Are Not Uniform

Some settings are normalized aggressively and some are not.

- `reactive_color` is normalized through `normalize_rgb_triplet()`.
- `color` is stored as `list(value)` and returned as `tuple(self._settings["color"])` without the same normalization.
- boolean helpers use generic truthiness, so a non-empty string like `"false"` would still read as `True` if it reached the config layer.

This does not necessarily mean current behavior is wrong; it means the contracts live in a diffuse set of helper functions rather than in typed constructors that make valid state explicit.

### 5. Snapshot Data Gets Rebuilt As Dicts At Each Boundary

KeyRGB already has one good example of a typed runtime snapshot in `ConfigApplyState`, but the pattern is not applied consistently.

- diagnostics config snapshots are anonymous dicts
- support-window probe snapshots are anonymous dicts
- nested diagnostics sections are anonymous dicts and lists of dicts

That makes snapshot evolution harder because every key rename or new field depends on manual coordination instead of one typed definition.

## Evidence From The Codebase

- `src/core/config/defaults.py` defines a single large `DEFAULTS` dict that mixes durable preferences, compatibility fields, UI selection state, and restore-oriented state. Examples include `secondary_device_state`, `return_effect_after_effect`, and `tray_device_context` alongside normal user preferences.
- `src/core/config/file_storage.py` loads config by deep-copying defaults, loading raw JSON, lowercasing only a few known string fields, mapping removed effect names to `none`, then `update()`-merging loaded values into the defaults copy. The merge is flexible, but it means the runtime config shape is still fundamentally a loose mapping.
- `src/core/config/config.py` stores runtime settings in `self._settings: dict[str, Any]` and manipulates keys directly for `effect`, `speed`, `return_effect_after_effect`, and `effect_speeds`. The object is a helpful API boundary, but the internal model remains a mutable bag of fields.
- `src/core/config/_lighting/_coercion.py` mutates the loaded settings mapping in place, normalizes several brightness families with different rules, and reads the raw config file again to detect whether `perkey_brightness` existed on disk. That second read is concrete evidence that the runtime mapping is missing "presence" information that some coercion paths care about.
- `src/core/config/_lighting/_props.py` and `src/core/config/_lighting/_lighting_accessors.py` encode many contracts through repeated string-key reads. `brightness` branches on whether the current effect is `perkey`; `reactive_brightness` falls back to `brightness`; secondary-device accessors walk through normalized route keys, nested dict lookups, default lookup keys, and compatibility keys.
- `src/core/config/_lighting/_lighting_accessors.py` also shows contract inconsistency across fields. `reactive_color` is normalized defensively, while `color` is a much thinner accessor. `tray_device_context` and `layout_legend_pack` each implement their own normalization logic inline.
- `src/gui/settings/settings_state.py` is a positive counterexample. It loads config into a typed `SettingsValues` dataclass, handles the `power_management_enabled` / `management_enabled` alias once, derives effective AC and battery brightness values, then applies that typed state back onto config. This is the clearest in-repo precedent for an incremental migration.
- `src/core/power/management/manager.py`, `src/core/power/management/_manager_helpers.py`, and `src/core/power/policies/power_source_loop_policy.py` show another positive precedent. The power manager still reads from config defensively, but once the values are assembled they become a typed `PowerSourceLoopInputs` dataclass with a typed `PowerSourceLoopResult` output.
- `src/tray/pollers/config_polling_internal/core.py` defines a frozen `ConfigApplyState` dataclass, which is a good runtime snapshot. At the same time, `compute_config_apply_state()` still has to rebuild that state through `safe_*` attribute reads and ad-hoc tuple coercion because callers cannot rely on the underlying config object exposing one stable typed snapshot directly.
- The same tray poller module manually compares many individual fields in `maybe_apply_fast_path()` to detect "only target changed," "only reactive settings changed," and "only brightness changed." A richer typed snapshot model could move some of that branching closer to the state itself.
- `src/core/diagnostics/model.py` uses a typed top-level dataclass, but most nested fields are still `dict[str, Any]` or `list[dict[str, Any]]`. `src/core/diagnostics/collectors/__init__.py` builds the config section through a string whitelist and anonymous `out` / `settings` dicts. The top-level shell is typed; the nested payloads are still open-ended.
- `src/gui/windows/_support/_support_window_jobs.py` snapshots and restores probe-related config as `{"effect": ..., "speed": ..., "effect_speeds": ...}`. That is small and isolated, which makes it a good candidate for an early typed-model migration.

Representative tests reinforce that these contracts already matter:

- `tests/core/config/test_config_helpers_unit.py` covers coercion of missing `perkey_brightness`, precise reactive brightness, malformed JSON, and save callback behavior.
- `tests/core/config/test_config_unit.py` covers corrupt `effect_speeds`, invalid `tray_device_context`, lightbar fallback behavior, per-mode brightness handling, and defensive accessors.
- `tests/tray/pollers/config/runtime/test_tray_config_polling_state_misc_unit.py` verifies that `ConfigApplyState` assembly still has to tolerate property exceptions and odd shapes.
- `tests/core/diagnostics/core/test_diagnostics_unit.py` verifies config snapshot sanitization and boundary behavior.
- `tests/gui/windows/test_support_window_unit.py` verifies the support-window snapshot/restore flow for `effect`, `speed`, and `effect_speeds`.

## Candidate Typed-Model Seams

The best migration targets are not giant "type the whole config" rewrites. They are small seams where one typed model can replace repeated dict handling.

### 1. A Normalized Persisted-Config Model Behind `Config`

Introduce an internal parse/serialize model for the config file, for example `NormalizedConfigData` or similarly named dataclasses. The goal would not be to change the JSON file format immediately. The goal would be:

- parse `dict[str, Any]` once
- normalize fields once
- preserve unknown keys in an `extras` mapping if forward compatibility is needed
- serialize back to the same flat JSON shape for now

This would give `Config` a typed core while preserving the existing disk contract.

### 2. A Typed Lighting-Preferences Model

There is enough related logic around effect, speed, brightness, reactive settings, direction, and software-target routing to justify a typed grouping. This could be one dataclass or a few small value objects, for example:

- base lighting state
- reactive lighting options
- per-effect speed overrides

The main benefit would be consolidating today’s repeated fallback rules around `brightness`, `perkey_brightness`, `reactive_brightness`, `reactive_trail_percent`, `color`, and `software_effect_target`.

### 3. Typed Wrappers For Nested String-Keyed Maps

Two places stand out:

- `effect_speeds`
- `secondary_device_state`

These do not need heavy machinery. Small wrapper objects such as `EffectSpeedOverrides` and `SecondaryDeviceStateEntry` would already improve things. Their job would be to own normalization and serialization, so callers no longer have to remember whether a value might be a corrupt string, a missing dict, or an in-compatibility fallback case.

### 4. Typed Snapshot Models For Runtime Helpers

`ConfigApplyState` proves the value of a typed snapshot. The same idea should be extended to the smaller ad-hoc snapshots that still use dicts.

Good candidates:

- support-window probe snapshots for `effect`, `speed`, and `effect_speeds`
- diagnostics config snapshots, including `present`, `mtime`, filtered settings, and `per_key_colors_count`

These models would be read-only and easy to compare in tests.

### 5. A Typed Power-And-Display Settings View

`SettingsValues` already reads and writes a coherent set of power-management and dim-sync settings. That could become a broader shared model used by:

- settings UI
- power manager
- diagnostics config snapshots
- future config migration work

This is attractive because the code already has alias handling and effective-brightness derivation logic there. It is not speculative architecture; it is consolidating an existing success pattern.

### 6. Optional Small Value Objects For Repeated Primitives

If the team wants to go a step further later, a small RGB triplet value object or a device-context identifier type could reduce repeated `tuple` / `list` / `str(...).strip().lower()` conversions. This is a secondary seam, not the first one to pursue.

## Low-Risk Versus High-Risk Migrations

### Low-Risk Migrations

- add read-only dataclasses for runtime and diagnostics snapshots while keeping their serialized forms unchanged
- add tiny typed wrappers around `effect_speeds` and secondary-device entries, with explicit `from_dict()` / `to_dict()` conversion helpers
- reuse or expand `SettingsValues` as a shared typed view for power-management and dim-sync settings
- introduce an internal normalized config model behind `Config` while still storing the same flat JSON on disk
- centralize alias handling in one place instead of letting power-management callers keep checking both `power_management_enabled` and `management_enabled`

These changes are low-risk because they narrow ambiguity without forcing a persisted-schema migration.

### High-Risk Migrations

- replacing `Config._settings` everywhere in one pass
- changing the JSON schema for `secondary_device_state`, `per_key_colors`, or top-level compatibility keys immediately
- enforcing strict effect enums too early, since the loader currently accepts older and backend-specific names and normalizes them pragmatically
- deep-typing every diagnostics section in one sweep; the backend and system collectors are intentionally heterogeneous, so a broad conversion would carry a higher coordination cost
- treating all currently persisted state as pure user preference; some fields are session-ish or compatibility-oriented, and flattening those distinctions too early could break behavior

## Recommended First Steps


1. Add a small typed snapshot for support-window probe state.

   `src/gui/windows/_support/_support_window_jobs.py` is isolated, has focused tests, and already snapshots only three fields. Converting that dict to a dataclass would be a safe first use case.

2. Add a typed diagnostics config snapshot model.

   `src/core/diagnostics/model.py` already provides a top-level dataclass. Adding a typed nested model for the `config` section would be consistent with the existing design and would shrink one of the more visible anonymous payloads.

3. Wrap `effect_speeds` and `secondary_device_state` before attempting a whole-config model.

   These are high-value because they currently require shape checks and fallback behavior in multiple places. They are also easy to serialize back to the current JSON format.

4. Promote the `SettingsValues` pattern into a shared config-view layer.

   The settings UI has already proven that a typed read/apply boundary works well. Reusing that pattern for power-management and dim-sync readers would consolidate aliases and derived defaults without disturbing unrelated config areas.

5. Only then introduce a normalized config model behind `Config`.

   By that point the codebase will already have typed seams for snapshots and nested maps, which reduces the blast radius of making `Config` itself less dict-centric.

## Validation Strategy

Any migration in this area should be validated as a behavior-preserving refactor first.

- keep the on-disk JSON schema stable during the first phases and assert round-trips back to equivalent persisted data
- add parser/serializer tests for every new typed model, especially around malformed, missing, and compatibility-shaped input
- preserve existing targeted tests in `tests/core/config/`, `tests/tray/pollers/config/`, `tests/core/diagnostics/core/`, and `tests/gui/windows/test_support_window_unit.py` as regression guards
- add differential tests where old dict-based helpers and new typed helpers are run against the same fixture payloads and expected to produce the same normalized results
- verify unknown-key preservation explicitly if a normalized config model introduces an `extras` bag
- keep diagnostics sanitization tests in place so typed snapshots do not accidentally leak full paths or large per-key payloads
- treat alias compatibility as a first-class contract; any new typed view should prove that `power_management_enabled` / `management_enabled` and legacy lightbar keys still behave as intended until the repo deliberately chooses to retire them

The best success criterion is simple: fewer `dict.get()` chains and fewer repeated normalization branches outside the config boundary, with no change to current user-visible behavior.
