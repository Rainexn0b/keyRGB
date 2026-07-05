# Lane Registry

This file is the authoritative list of documentation lanes. It complements the
top-level `docs/README.md`.

## Rules

- A lane identifier is either a single character (`0–9`, `A–Z`) or `<single-char>-<kebab-topic>`.
- Lane identifiers are permanent. New topics use the next free identifier; we do not renumber.
- Archived docs that remain relevant to an active lane live in `<lane>/archived/<YYYY-MM-DD>/`.
- Obsolete docs and disbanded lanes live in `Z-legacy/`.

## Registry

| Lane | Purpose | Status | Current source |
|---|---|---|---|
| `0-usage` | User-facing usage, setup, and troubleshooting guides | active | `docs/usage/` |
| `0-project` | Release/commit procedure, repo shape, contribution guidelines | planned | `docs/usage/02-commit_procedure.md`, `docs/usage/03-release_procedure.md` |
| `A-architecture` | System architecture, module inventory, build-system design | active | `docs/architecture/` |
| `B-backend-audits` | Backend audit reports and reference comparisons | active | `docs/B-backend-audits/` |
| `B-hardware-research` | Hardware expansion research and device-support investigations | active | `docs/genAI/research-device-support/` |
| `B-backend-guides` | Backend-specific implementation plans and protocol notes | active | `docs/developement/backends/` |
| `D-development` | Active development plans, refactor campaigns, and architecture specs | active | `docs/developement/` |
| `D-bug-reports` | Bug investigations and retest records | active | `docs/developement/bug-reports/`, `docs/developement/bug-ongoing/` |
| `O-debugging` | Debugging notes, incident records, and runbooks | active | `docs/debugging/` |
| `Q-tech-debt` | Tech-debt ledgers, quality campaigns, and test strategy | active | `docs/tech-debt/` |
| `Z-legacy` | Obsolete docs, disbanded lanes, superseded records | legacy | `docs/Z-legacy/` |

## Reserved buckets

`1–9` (except `0`), `C`, `E–G`, `I–N`, `P–T`, `V–Y` are reserved.
