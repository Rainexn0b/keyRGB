# KeyRGB Documentation

This directory contains canonical project documentation. The docs are organized
into **lanes**: stable, prefixed buckets and hyphenated sub-lanes.

## Lane ID grammar

```text
N                 → top-level bucket index / overview (0-9, A-Z)
N-<topic>         → specific topic lane, kebab-case (e.g. B-backend-audits)
N-<topic>/<sub>   → optional one-level sub-folder for large topics
N-<topic>/archived/<YYYY-MM-DD>/  → archive bucket inside the lane
Z-legacy/         → terminal bucket for obsolete docs and disbanded lanes
```

- Lanes are stable addresses. Once assigned, they do not change.
- Archived docs that are still relevant to an active lane live inside `<lane>/archived/`.
- Legacy / obsolete docs live in `Z-legacy/`.

## Lane registry

### `0` — Project meta

| Lane | Purpose |
|---|---|
| `0-governance` | Documentation governance and lane registry |

### `1` — Architecture & technical reference

| Lane | Purpose |
|---|---|
| `1-buildpython` | Build system (`buildpython`) design and operation |
| `1-repo` | Repository layout and conventions |
| `1-src` | Source-code architecture (backends, tray, diagnostics, etc.) |

### `2` — Usage & operations

| Lane | Purpose |
|---|---|
| `2-usage` | User-facing usage, setup, troubleshooting, release/commit procedures |

### `9` — Legal / project policy

| Lane | Purpose |
|---|---|
| `9-Legal` | Code of conduct and legal/project-policy docs |

### `B` — Backends & hardware research

| Lane | Purpose |
|---|---|
| `B-backend-audits` | Backend audit reports and reference comparisons |
| `B-backend-guides` | Backend implementation plans, protocol notes, and naming policy |
| `B-Research` | Hardware expansion research and device-support investigations |

### `D` — Development & debugging

| Lane | Purpose |
|---|---|
| `D-bug-reports` | Bug investigations and retest records |
| `D-debugging` | Debugging notes, incident records, and runbooks |

### `I` — Implementation plans

| Lane | Purpose |
|---|---|
| `I-implementation-plans` | Bounded implementation and refactor campaign plans |

### `O` — Optimisations

| Lane | Purpose |
|---|---|
| `O-optimisations` | Performance, stability, and footprint improvement plans |

### `P` — Power management

| Lane | Purpose |
|---|---|
| `P-power-management` | Power-mode, battery-saver, and idle-power specs |

### `R` — Feature removals

| Lane | Purpose |
|---|---|
| `R-feature-removals` | Pruning and deprecation plans |

### `U` — GUI / UX

| Lane | Purpose |
|---|---|
| `U-gui` | GUI and user-experience work |

### `Z` — Legacy

| Lane | Purpose |
|---|---|
| `Z-legacy` | Obsolete docs, disbanded lanes, superseded records |

## Reserved buckets

Buckets `3–8`, `C–H`, `J–N`, `Q`, `S–T`, `V–Y` are reserved for future use.

## Adding a new lane

1. Pick the next free bucket or sub-lane name from the registry above.
2. Add it to this README and to `0-governance/lane-registry.md`.
3. Create the directory and a `README.md` explaining scope.
4. Do not renumber existing lanes.
