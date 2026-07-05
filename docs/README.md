# KeyRGB Documentation

This directory contains canonical project documentation. The docs are organized
into **lanes**: stable, prefixed buckets and hyphenated sub-lanes. The scheme is
a lightweight adaptation of the doc-lanes pattern; we keep fewer buckets than a
large monorepo because the project surface is smaller.

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

| Lane | Purpose | Current source (if migrating) |
|---|---|---|
| `0-usage` | User-facing usage, setup, and troubleshooting guides | `docs/usage/` |
| `0-project` | Release/commit procedure, repo shape, contribution guidelines | `docs/usage/02-commit_procedure.md`, `docs/usage/03-release_procedure.md`, `CONTRIBUTING.md` |

### `A` — Architecture

| Lane | Purpose | Current source |
|---|---|---|
| `A-architecture` | System architecture, module inventory, build-system design | `docs/architecture/` |

### `B` — Backends & hardware

| Lane | Purpose | Current source |
|---|---|---|
| `B-backend-audits` | Backend audit reports and reference comparisons | `docs/audit/` |
| `B-hardware-research` | Hardware expansion research and device-support investigations | `docs/genAI/research-device-support/` |
| `B-backend-guides` | Backend-specific implementation plans and protocol notes | `docs/developement/backends/` |

### `D` — Development

| Lane | Purpose | Current source |
|---|---|---|
| `D-development` | Active development plans, refactor campaigns, and architecture specs | `docs/developement/` (note: directory name retains historical spelling) |
| `D-bug-reports` | Bug investigations and retest records | `docs/developement/bug-reports/`, `docs/developement/bug-ongoing/` |

### `O` — Operations

| Lane | Purpose | Current source |
|---|---|---|
| `O-debugging` | Debugging notes, incident records, and runbooks | `docs/debugging/` |

### `Q` — Quality

| Lane | Purpose | Current source |
|---|---|---|
| `Q-tech-debt` | Tech-debt ledgers, quality campaigns, and test strategy | `docs/tech-debt/` |

### `Z` — Legacy

| Lane | Purpose |
|---|---|
| `Z-legacy` | Obsolete docs, disbanded lanes, and superseded records |

## Reserved buckets

Buckets `1–9` (except `0`), `C`, `E–G`, `I–N`, `P–T`, `V–Y` are reserved for
future use.

## Adding a new lane

1. Pick the next free bucket or sub-lane name from the registry above.
2. Add it to this README and to `0-governance/lane-registry.md`.
3. Create the directory and a `README.md` explaining scope.
4. Do not renumber existing lanes.
