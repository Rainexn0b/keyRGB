# Lane Registry

This file is the authoritative list of documentation lanes. It complements the
top-level `docs/README.md`.

## Rules

- A lane identifier is either a single character (`0–9`, `A–Z`) or `<single-char>-<kebab-topic>`.
- Lane identifiers are permanent. New topics use the next free identifier; we do not renumber.
- Archived docs that remain relevant to an active lane live in `<lane>/archived/<YYYY-MM-DD>/`.
- Obsolete docs and disbanded lanes live in `Z-legacy/`.

## Registry

| Lane | Purpose | Status |
|---|---|---|
| `0-governance` | Documentation governance, lane registry | active |
| `1-buildpython` | Build system (`buildpython`) design and operation | active |
| `1-repo` | Repository layout and conventions | active |
| `1-src` | Source-code architecture | active |
| `2-usage` | User-facing usage, setup, troubleshooting, release/commit procedures | active |
| `9-Legal` | Code of conduct and legal/project-policy docs | active |
| `B-backend-audits` | Backend audit reports and reference comparisons | active |
| `B-backend-guides` | Backend implementation plans, protocol notes, and naming policy | active |
| `B-Research` | Hardware expansion research and device-support investigations | active |
| `D-bug-reports` | Bug investigations and retest records | active |
| `D-debugging` | Debugging notes, incident records, and runbooks | active |
| `I-implementation-plans` | Bounded implementation and refactor campaign plans | active |
| `O-optimisations` | Performance, stability, and footprint improvement plans | active |
| `P-power-management` | Power-mode, battery-saver, and idle-power specs | active |
| `R-feature-removals` | Pruning and deprecation plans | active |
| `U-gui` | GUI and user-experience work | active |
| `Z-legacy` | Obsolete docs, disbanded lanes, superseded records | legacy |

## Reserved buckets

`3–8`, `C–H`, `J–N`, `Q`, `S–T`, `V–Y` are reserved.
