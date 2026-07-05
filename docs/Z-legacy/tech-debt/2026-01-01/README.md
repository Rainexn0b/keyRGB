# Tech debt (maintainability)

This folder tracks known maintainability issues, refactor proposals, and “hot spots” (large or high-churn modules).

**Goals**

- Keep the codebase approachable for contributors.
- Reduce risk when adding features (diagnostics, settings, power logic, new devices).
- Make it easier to test core behavior without hardware.

**How to use these docs**

- Start with [Hotspots](./hotspots.md) for the current “largest / riskiest” modules.
- Use [Tracking](./tracking.md) as the living backlog of refactors.
- Use [Refactor plan](./refactor-plan.md) for concrete suggested PR slices.
- See [Legacy boundaries](./legacy-boundaries.md) for what is considered “legacy” in this repo.

**Update cadence**

- Update `hotspots.md` when a file is split/merged or a new module becomes large.
- Update `tracking.md` when starting/finishing a refactor.

**Snapshot metadata**

- Last updated: 2025-12-29
- Metric source: `wc -l` (lines of code, approximate)
