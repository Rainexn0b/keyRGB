# Lane Registry

This file is the authoritative list of documentation lanes.

## Rules

- A lane identifier is either a single character (`0–9`, `A–Z`) or `<single-char>-<kebab-topic>`.
- Lane identifiers are permanent. New topics use the next free identifier; we do not renumber.
- Archived docs that remain relevant to an active lane live in `<lane>/archived/<YYYY-MM-DD>/`.
- Legacy / obsolete docs live in `Z-legacy/`. Inside `Z-legacy/`, categories are filed as `Z-legacy/<category>/<YYYY-MM-DD>/`.

## Lane registry

| Lane | Purpose | Status |
|---|---|---|
| `0-governance` | Documentation governance and this registry | active |
| `1-buildpython` | Build system (`buildpython`) design and operation | active |
| `1-repo` | Repository layout and conventions | active |
| `1-src` | Source-code architecture | active |
| `2-usage` | User-facing usage, setup, troubleshooting | active |
| `3-contributing` | Contributor workflow: build runner, commit/release procedures | active |
| `9-Legal` | Code of conduct and legal/project-policy docs | active |
| `B-backend-audits` | Backend audit reports and reference comparisons | active |
| `B-backend-guides` | Backend implementation plans, protocol notes, naming policy | active |
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

`4–8`, `C–H`, `J–N`, `Q`, `S–T`, `V–Y` are reserved for future use.

## Adding a new lane

1. Pick the next free bucket or sub-lane name from the registry above.
2. Update this file and `0-governance/README.md`.
3. Create the directory and a `README.md` explaining scope.
4. Do not renumber existing lanes.

## Legacy disposition rules

- Move obsolete docs into `Z-legacy/` rather than deleting them.
- File legacy docs under `Z-legacy/<category>/<YYYY-MM-DD>/`.
- Rename files with a `YYYY-MM-DD-` prefix when the obsolescence date matters.
- Update any internal links that still point to the old location.
