# Backend naming

KeyRGB backend names should stay stable across laptop rebrands, vendor SKUs, and
support reports. Use these rules when adding or splitting a backend.

## Primary rule

Name the backend after the controller family **and** the lighting capability it
exposes. This keeps the backend identity attached to the packet and capability
model rather than a laptop marketing name.

```text
ITE<chip>_<capability>[_<capability>...][_<oem>]
```

**Canonical rules (including the hard max-four post-chip appendages limit and
coarse chassis tokens) live in**
[`src/core/backends/README.md`](../../src/core/backends/README.md).
Do not invent longer surface-inventory names; put logo/neon/vent detail on
secondary routes and in support docs.

Capabilities are ordered **`chassis` > `zones` > `perkey`**.

Examples already in tree:

- `ite8291r3_perkey`
- `ite8291_perkey`
- `ite8291_zones_clevo`
- `ite8295_zones_lenovo_ideapad`
- `ite8258_zones_lenovo_legion`
- `ite8258_perkey_chassis`
- `ite8233_none_chassis_lightbar_clevo`
- `ite8297_uniform`
- `ite8910_perkey`

## Capability suffixes

| Suffix | Meaning |
|--------|---------|
| `_perkey` | Every key is individually addressable |
| `_zones` | Keyboard deck has 2+ controllable zones, but not per-key |
| `_uniform` | Entire keyboard is one single color |
| `_chassis` | Non-keyboard lighting (logo, vents, neon strips) |
| `_lightbar` | A separate lightbar strip device |

All ITE backend names use **underscores** exclusively. Non-ITE backends
(`sysfs-leds`, `sysfs-mouse`, `asusctl-aura`) retain hyphens because they do
not follow the `ITE<chip>` convention.

## When to add a qualifier

Add a capability suffix when one controller family splits into incompatible
runtime shapes that need separate backend ownership.

Current examples:

- `ite8291_perkey` vs `ite8291_zones_clevo`
- `ite8258_zones_lenovo_legion` vs `ite8258_perkey_chassis`

These are split because they use different protocols, different HID interfaces,
or different probe behavior.

## What not to use as the primary name

Do not use laptop or SKU names as the main backend identifier.

Keep those in:

- README coverage notes
- support docs and research plans
- diagnostics wording
- tests and evidence bundles

Also avoid raw numbered variants such as `var1`, `var01`, or `v01` as public
backend names when the split is already understood. Numbered variants are
acceptable only as temporary research or catalogue labels while evidence is still
incomplete. Replace them with a semantic qualifier before exposing the backend
publicly.

## Python package vs public backend name

Python package directories use underscores and match the public backend name.

Examples:

- package: `ite8291_zones_clevo` → backend name: `ite8291_zones_clevo`
- package: `ite8295_zones_lenovo_ideapad` → backend name: `ite8295_zones_lenovo_ideapad`
- package: `ite8291r3_perkey` → backend name: `ite8291r3_perkey`

## Deprecated aliases

Renamed backends keep backward-compatible aliases so existing user config
(`KEYRGB_BACKEND`, saved profiles) continues to work. Aliases are resolved in
`src/core/backends/registry.py::_BACKEND_NAME_ALIASES`.

See `src/core/backends/README.md` for the full alias table and policy.

## Current `ite8258` direction

- `ite8258_zones_lenovo_legion` for the keyboard-only `0x048d:0xc195` 24-zone path
- `ite8258_perkey_chassis` for the `0x048d:0xc197` composite chassis-lighting path

If a future `ite8258` split appears before its semantics are fully understood, a
numbered research label can exist in notes temporarily, but the public backend
name should still be renamed to a semantic form before release.
