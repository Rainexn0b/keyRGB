# Backend naming

KeyRGB backend names should stay stable across laptop rebrands, vendor SKUs, and support reports.

Use these rules when adding or splitting a backend.

## Primary rule

Name the backend after the controller family or protocol family that defines the runtime contract.

Examples already in tree:

- `ite8258`
- `ite8291`
- `ite8291r3`
- `ite8910`

This keeps the backend identity attached to the packet and capability model rather than a laptop marketing name.

## When to add a qualifier

Add a qualifier only when one controller family splits into incompatible runtime shapes that need separate backend ownership.

Prefer semantic qualifiers that explain the split:

- topology or surface split: `-zones`, `-lightbar`, `-chassis`
- protocol or hardware revision split: `r3`

Current examples:

- `ite8291` vs `ite8291-zones`
- `ite8295-zones`
- `ite8291r3`

## What not to use as the primary name

Do not use laptop or SKU names as the main backend identifier.

Keep those in:

- README coverage notes
- support docs and research plans
- diagnostics wording
- tests and evidence bundles

Also avoid raw numbered variants such as `var1`, `var01`, or `v01` as public backend names when the split is already understood.

Numbered variants are acceptable only as temporary research or catalogue labels while evidence is still incomplete. Replace them with a semantic qualifier before exposing the backend publicly.

## Python package vs public backend name

Python package directories should stay import-safe and use underscores when needed.

Examples:

- package: `ite8291_zones` -> backend name: `ite8291-zones`
- package: `ite8295_zones` -> backend name: `ite8295-zones`

Follow the same pattern for future splits.

## Current `ite8258` direction

- keep `ite8258` for the existing keyboard-only `0x048d:0xc195` 24-zone path
- use `ite8258-chassis` for the `0x048d:0xc197` composite keyboard-plus-chassis-lighting path

If a future `ite8258` split appears before its semantics are fully understood, a numbered research label can exist in notes temporarily, but the public backend name should still be renamed to a semantic form before release.