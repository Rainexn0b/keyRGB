# Backend emulation package

Date: 2026-09-19  
Status: implemented (phase 1–3); phase 4 inspector deferred   
Owner: `keyrgb/core/backends/` (emulation seam) with consumers in tray, editor, diagnostics  
Related: issue #13 4-zone + Tongfang lightbar UX; existing `KEYRGB_SIMULATE_SECONDARY_DEVICES`

## Status

Phases 1–3 implemented. `KEYRGB_EMULATE` intercepts primary selection and
secondary-route acquisition. Local UX confirmation: 4-zone Lighting Profile
Editor and named auxiliary simulation work without hidraw
(`preset:beast-x30`). Phase 4 inspector remains deferred.

This is UX and automated-test validation only. Emulation must never be reported
as hardware detection and must never be used as evidence to promote an
experimental backend.

## Why this exists

Issue #13 (MEDION ERAZER Beast X30) needs a click-through session of:

- experimental 4-zone keyboard (`ite8291_zones_clevo`, `zoned=True`, `1x4`)
- experimental Tongfang front lightbar (`ite8291_none_chassis_lightbar_tongfang`)
- Lighting profile toggle, software effects, lighting editor, zone paint,
  AC/battery automation, independent lightbar brightness

Today those paths require real hidraw. The only hardware-free mode is:

```bash
KEYRGB_SIMULATE_SECONDARY_DEVICES=1 ./keyrgb.sh
```

That flag:

- fakes **every** secondary route (Clevo lightbar, Tongfang lightbar, mouse,
  logo, neon, vents) as the same 1×1 uniform device
- leaves primary keyboard selection and I/O unchanged (`NullKeyboard` if none)
- cannot advertise `zoned=True` to the tray, so the 4-zone editor/menu work
  cannot be exercised
- cannot represent a compatible *scene* (one keyboard + one matching lightbar)

`KEYRGB_PERKEY_PREFLIGHT` can lie to the editor subprocess about capabilities.
That is a launch hook, not an emulator. Tray menus still follow the real
backend.

## Executive decision

1. Put emulation on the **backend registry / probe seam**, not beside it.
2. Key emulation by **canonical backend name**, using existing aliases.
3. Allow **one PRIMARY** plus **zero or more compatible AUXILIARY** backends.
4. Drive `capabilities()`, `dimensions()`, and device protocol from the real
   backend contract. Do not invent a second capability model.
5. Replace `KEYRGB_SIMULATE_SECONDARY_DEVICES=1` with an explicit list
   (`KEYRGB_EMULATE=...`), keeping a one-release compatibility mapping.
6. Fail closed on unknown names, two PRIMARYs, or an AUXILIARY whose parent is
   missing.
7. Label every emulated probe, tray row, diagnostic snapshot, and support
   bundle as `emulated`. Never as `detected` or `supported hardware`.

The short design rule is: **emulate backends, not a fake laptop.**

## Current seams to wrap

```text
KEYRGB_BACKEND / auto
    -> registry.build_backend_selection_report
        -> PRIMARY KeyboardBackend.probe / get_device
            -> tray.backend_caps, effect geometry, lighting editor preflight

iter_secondary_routes
    -> secondary_device_runtime.iter_effective_secondary_routes
        -> AUXILIARY probe / acquire_secondary_device
            -> tray contexts, lighting areas, software-effect fan-out
```

Emulation intercepts both boxes. Tray, editor, profiles, effects, and
diagnostics keep consuming the same facades.

Do not add:

- a parallel `EmulatedTray`
- editor-only preflight lies as the long-term 4-zone UX path
- HID/sysfs path overrides as “safe simulation” (they still open nodes)

## Compatibility model

Reuse `BackendRole` and secondary route metadata.

### Allowed

- At most one `BackendRole.PRIMARY`.
- Any number of `BackendRole.AUXILIARY` that do not share a conflicting
  identity with the primary or each other.
- Virtual child routes only when their `parent_backend_name` PRIMARY is in
  the emulate set (`ite8258_perkey_chassis` logo/neon/vent).

### Forbidden

- Two PRIMARYs (`ite8291r3_perkey` + `ite8291_zones_clevo`).
- Same USB identity, different firmware dialect (`048d:ce00` per-key vs
  `bcdDevice 0x0002` 4-zone).
- An AUXILIARY whose parent PRIMARY is not emulated.
- Auto-selection of emulated backends when `KEYRGB_EMULATE` is unset.

Two standalone lightbars (`ite8233` Clevo and `ite8291` Tongfang) share
`device_type="lightbar"` but have distinct `backend_name` / `state_key`.
They may be listed together only for UI stress tests. Default presets must
not enable both.

### First presets

| Preset | Backends | UX to validate |
|---|---|---|
| `preset:beast-x30` | `ite8291_zones_clevo` + `ite8291_none_chassis_lightbar_tongfang` | Issue #13 4-zone editor, Lighting profile toggle, Front Lightbar |
| `preset:legion-gen10` | `ite8258_perkey_chassis` | Per-key keyboard + logo/neon/vent virtual routes |
| `preset:perkey-clevo-bar` | `ite8291r3_perkey` + `ite8233_none_chassis_lightbar_clevo` | Per-key editor + Clevo lightbar |
| `preset:uniform` | `sysfs-leds` | Brightness/color-only tray (no Lighting profile editor) |

Presets are aliases for an explicit name list. Unknown preset names fail closed.

## Control surface

### Environment

```bash
KEYRGB_EMULATE=ite8291_zones_clevo,ite8291_none_chassis_lightbar_tongfang \
KEYRGB_CONFIG_DIR=/tmp/keyrgb-ux-sim \
KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 \
KEYRGB_DEBUG=1 \
./keyrgb.sh
```

Or:

```bash
KEYRGB_EMULATE=preset:beast-x30 \
KEYRGB_CONFIG_DIR=/tmp/keyrgb-ux-sim \
./keyrgb.sh
```

Rules:

- Empty / unset: no emulation (production probe path).
- Comma-separated canonical names or documented aliases.
- `preset:<id>` expands before validation.
- `*` is reserved as the compatibility expansion of the old “all secondaries,
  no primary” flag. Do not use it in new docs or presets.
- Inherit into editor, uniform, calibrator, and settings subprocesses the same
  way `KEYRGB_SIMULATE_SECONDARY_DEVICES` is inherited today.
- Isolate config/profiles with `KEYRGB_CONFIG_DIR` for manual sessions.
- Emulation does not require real hidraw. Experimental backends still show as
  experimental in the UI; the hardware opt-in gate is skipped only because no
  device node is opened.

### Compatibility shim

For one release:

| Old | New |
|---|---|
| `KEYRGB_SIMULATE_SECONDARY_DEVICES=1` | `KEYRGB_EMULATE=*` (all AUXILIARY routes, no PRIMARY) |
| Both set | `KEYRGB_EMULATE` wins; log a warning |

After the shim window, keep the old variable as an alias that logs
deprecation, then remove it.

### Non-goals for the flag

- No Settings toggle in v1. Env-only, matching the current simulation contract.
- No `KEYRGB_BACKEND=emulated`. `KEYRGB_BACKEND` remains a real-or-emulated
  primary selector *inside* the emulate set.
- No silent fallback to real hardware if an emulated open fails.

## Package shape

New owner, not a tray module:

```text
keyrgb/core/backends/emulation/
    __init__.py          # parse_emulate_spec, emulation_enabled, public facade
    spec.py              # EmulationSpec, presets, alias resolution, validation
    compatibility.py     # one PRIMARY, parent/child, USB-identity conflicts
    devices.py           # in-memory KeyboardDevice matching caps/dimensions
    primary.py           # wrap select_backend / probe for listed PRIMARY
    auxiliary.py         # replace all-or-nothing secondary simulation
```

Keep protocol encoding in each real backend package. Emulation must not import
hidraw open paths.

### `EmulationSpec`

```text
EmulationSpec {
  raw: str
  names: tuple[str, ...]          # canonical backend names
  primary: str | None
  auxiliary: tuple[str, ...]
  preset: str | None
  source: "emulate" | "legacy_secondary_simulate"
}
```

Parse once per process. Invalid spec raises at startup (tray logs and refuses
to pretend hardware exists). Tests inject a spec directly.

### In-memory device

One parameterized device, not a copy of each backend:

```text
EmulatedKeyboardDevice {
  backend_name: str
  capabilities: BackendCapabilities
  rows, cols: int
  framebuffer: dict[(row, col), (r, g, b)]
  brightness: int
  off: bool
}
```

Behaviour:

- `set_color` fills the framebuffer uniformly.
- `set_key_colors` writes cells that fit `rows x cols`; extra keys ignored.
- `set_brightness` / `turn_off` / `is_off` / `get_brightness` as today.
- `set_effect` raises `NotImplementedError` unless the wrapped backend
  advertises `hardware_effects` **and** a later phase adds a no-op catalog.
  v1: fail closed (same as `SimulatedUniformDevice`).
- `close` is idempotent.
- Auxiliary brightness uses the route’s `brightness_ui_max` (Tongfang 0..100
  stored, 0..50 hardware field at the real device; the emulator should accept
  the **stored** domain the tray already sends).

Capabilities and dimensions come from the real backend class methods when they
are pure. If a backend’s `capabilities()` or `dimensions()` currently open
hardware, add a static declaration on `BackendRegistration.metadata` or a
side-effect-free method rather than calling `get_device()`.

Preferred: extend `BackendMetadata` with optional:

```text
emulated_capabilities: BackendCapabilities | None
emulated_dimensions: tuple[int, int] | None
```

Populate for backends that need emulation in phase 2. Until then, instantiate
the backend class and call `capabilities()` / `dimensions()` only when those
methods are known not to open devices (true for ITE zone/per-key backends
today).

### Primary wrapper

`EmulatedPrimaryBackend`:

- `name` = canonical backend name (not `simulated:...`) so menus, preflight,
  and diagnostics stay on production identifiers
- `probe()` returns `available=True`, `reason="emulated"`, confidence 0,
  identifiers `{"emulated": "1", "backend": name}`
- `get_device()` returns the in-memory device
- `stability` copied from registration (experimental stays experimental)

Selection:

- If spec has a PRIMARY, `select_backend()` returns that wrapper. Ignore
  `KEYRGB_BACKEND=auto` ranking.
- If `KEYRGB_BACKEND` is set to a different PRIMARY than the spec, fail closed.
- If spec has no PRIMARY (`*` / legacy secondary-only), primary selection is
  unchanged (real probe or `NullKeyboard`).

### Auxiliary wrapper

Replace “simulate all routes” with:

- route is emulated iff its `backend_name` is in `spec.auxiliary` **or** its
  `parent_backend_name` is the emulated PRIMARY (virtual zones)
- `acquire_secondary_device` returns an in-memory uniform or zone device
- routes not in the spec are omitted (not probed)

Tongfang and Clevo lightbars keep distinct `state_key`s.

## Call-site changes (minimal)

| Seam | Change |
|---|---|
| `keyrgb/core/backends/_registry_selection.py` | If spec.primary: skip USB probe, return wrapper |
| `keyrgb/core/secondary_device_runtime.py` | Gate on spec.auxiliary instead of the boolean |
| `keyrgb/tray/ui/gui_launch.py` | Inherit `KEYRGB_EMULATE` (and shim) into subprocesses |
| `keyrgb/core/diagnostics/` | Snapshot the spec; mark probes `emulated` |
| tray status labels | `(emulated)` on primary and auxiliary rows |
| editor lighting areas | reuse existing simulation banner, driven by spec |

Tray `backend_caps` and editor preflight then follow the emulated PRIMARY.
No extra `KEYRGB_PERKEY_PREFLIGHT` is required for Beast X30 UX.

Architecture rules still apply: emulated devices are devices. Primary writes
stay under `kb_lock` and approved output owners. Secondary modules must not
write the primary framebuffer.

## Diagnostics and support bundles

- Env snapshot includes `KEYRGB_EMULATE` (redact nothing; it is not a secret).
- Probe identifiers include `emulated=1`.
- Support bundle summary must say emulation is active so issue reports cannot
  be mistaken for hardware evidence.
- Hardware tripwire tests: with `KEYRGB_EMULATE` set, hidraw/sysfs open paths
  for listed backends must not run.

## Tests

Phase 1 (auxiliary list):

- parse names, aliases, presets, fail-closed cases
- only listed auxiliary routes appear
- `KEYRGB_SIMULATE_SECONDARY_DEVICES=1` still exposes all AUXILIARY routes
- no real `get_device()` / hidraw open when emulated
- Tongfang-only spec does not create a Clevo lightbar row

Phase 2 (primary):

- `select_backend()` returns `ite8291_zones_clevo` wrapper with
  `zoned=True`, `per_key=False`, `dimensions==(1, 4)`
- tray menu: Lighting profile toggle enabled, Lighting Profiles visible
- editor bootstrap: zone paint, profiles, AC/battery vars present
- software `base_color_map` buckets a 6×21 profile onto 1×4
- `KEYRGB_BACKEND=ite8291r3_perkey` with spec primary `ite8291_zones_clevo`
  fails closed
- auto-selection without `KEYRGB_EMULATE` never returns a wrapper

Phase 3 (presets):

- `preset:beast-x30` expands to the two canonical names
- `preset:legion-gen10` exposes logo/neon/vent as virtual children
- unknown preset fails closed

Keep tests hardware-free. Do not set `KEYRGB_ALLOW_HARDWARE`.

## Manual acceptance (not hardware verification)

Beast X30 UX session:

```bash
KEYRGB_EMULATE=preset:beast-x30 \
KEYRGB_CONFIG_DIR=/tmp/keyrgb-ux-sim \
KEYRGB_DEBUG=1 \
./keyrgb.sh
```

Checklist:

- Keyboard status shows 4-zone / experimental, not “not detected”
- Software Effects → Lighting profile is enabled
- Lighting Profiles opens the editor; painting a key fills a zone
- AC/battery profile dropdowns work
- Front Lightbar is a separate context with independent brightness
- Include enabled lighting areas fans out without stealing lightbar brightness
- Support bundle / diagnostics say emulated
- A normal run without the flag has no emulation labels

Stop any other tray first so config dir and session sockets do not collide.

## Phased delivery

### Phase 1 — Named auxiliary emulation

- Add `emulation/spec.py` and parse `KEYRGB_EMULATE`
- Teach `secondary_device_runtime` to emulate listed AUXILIARY names only
- Shim the old boolean to `*`
- Inherit the new env into GUI subprocesses
- Tests: subset vs all, no hidraw, shim

Outcome: `KEYRGB_EMULATE=ite8291_none_chassis_lightbar_tongfang` shows only
Front Lightbar, not every chassis zone.

### Phase 2 — Primary emulator

- In-memory device + `EmulatedPrimaryBackend`
- Registry selection intercept
- Static caps/dimensions (metadata or pure methods)
- Tray/editor follow `backend_caps` with no preflight lies
- Tests: 4-zone caps, menu gating, fail-closed `KEYRGB_BACKEND` mismatch

Outcome: 4-zone Lighting profile toggle and editor work without hidraw.

### Phase 3 — Presets and compatibility matrix

- `preset:beast-x30`, `preset:legion-gen10`, `preset:perkey-clevo-bar`
- Explicit conflict table in `compatibility.py`
- Diagnostics wording and support-bundle banner

Outcome: one command for the issue #13 UX scene.

### Phase 4 — Optional inspector (deferred)

- Debug dump of emulated framebuffers
- Optional tiny preview window
- Not required for tray/editor validation

## Out of scope

- Claiming emulation is hardware validation or a substitute for issue #13
  reporter testing.
- New ITE USB IDs.
- Emulating hidraw permission failures, udev, or firmware sleep.
- A Settings UI toggle in v1.
- Visual RGB preview of the laptop.
- Changing production probe policy for real devices.

## Risks

- `capabilities()` / `dimensions()` that currently touch sysfs must not be
  called from the emulator constructor. Prefer metadata.
- Architecture keyword/lock gates must still see emulated writes as device
  I/O through approved owners.
- Tests that assume “simulate every secondary” need the `*` shim.
- Two processes with the same `KEYRGB_CONFIG_DIR` will fight; document
  isolation.
- Experimental UI copy must remain honest: emulated experimental is still
  experimental.

## Implementation notes for agents

- Put new code in `keyrgb/core/backends/emulation/` first.
- Do not edit `buildlog/` or `htmlcov/`.
- Preserve `pyproject.toml` entrypoints.
- Focused pytest: emulation spec, registry selection, secondary runtime,
  one tray menu slice, one editor bootstrap slice.
- If touching exception-transparency on the probe/open boundary, run
  `python -m buildpython --run-steps=19`.
- Do not open hidraw/sysfs in emulation tests.

## Success

A developer can run `KEYRGB_EMULATE=preset:beast-x30` on a machine with no ITE
device and click through 4-zone software effects, Lighting profile restore,
the lighting editor (zone paint, profiles, AC/battery), and Front Lightbar
independent brightness, with diagnostics clearly marked emulated.
