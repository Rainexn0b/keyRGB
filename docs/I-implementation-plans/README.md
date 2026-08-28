# I-implementation-plans — Implementation and refactor plans

**Scope:** Bounded implementation plans, refactor campaigns, and architecture
specs for larger changes.

## Documents

### Active sprint

- `2026-07-19/0.30.x-maintainability-sprint.md` — **0.30.x sprint umbrella**.
  Refactor-only patch series. The planned 0.30.2 work is complete: WS1, WS3,
  and WS4 are done, WS2 is monitoring after its highest-ROI slices, and WS5
  (legacy shim removal) remains blocked on profile-migration telemetry.

### Active follow-up plans

- `2026-08-11/architecture-concerns-plan.md` — confirmation and remediation
  tracker for the 2026-08-11 architecture review; one finding per pass, with
  test-first contracts and explicit confirmed/rejected status
- `2026-08-11/a2-tray-runtime-coordinator-design.md` — approval-gated FIFO
  coordinator, stale-observation revision, deferred UI, and migration design for
  A2 serialized tray runtime ownership
- `2026-07-16/0.30.1-maintainability-follow-up-plan.md` — **0.30.1** patch plan
  (done): top-3 residual weaknesses (orchestration purity, size hotspots,
  multi-layer tests) + bounded code-quality slices after 0.30.0
- `2026-07-15/maintainability-debt-paydown-plan.md` — full maintainability /
  tech-debt inventory (D1–D15), phases, and progress log
- `issue-7-composite-profile-hardening-and-validation-plan.md` — live-code-verified
  disposition of the v0.29.1 regression review, including desired/off semantics,
  composite output batching, the missing cross-layer regression, descriptor
  filtering, and reporter hardware gates

### Implemented dependencies / historical plans

- `2026-08-28/effect-and-backend-extension-friction.md` — implemented the
  registration-plus-test path for shipped software/reactive effects and the
  backend package-marker completeness tripwire, with no new visible effects
- `2026-08-27/dead-code-and-debloating-campaign.md` — completed W1–W9 across
  dead-code removal, dependency-source consolidation, facade auditing, and
  pure color-math deduplication; optional package-data/assets W10 remains
  deferred
- `secondary-lighting-profile-editor-and-simulation-plan.md` — implemented issue #7
  static scene/profile UX, tray target cleanup, and secondary-device simulation mode;
  reporter hardware validation remains pending and is tracked in the plan
- `ite8258-chassis-secondary-device-refactor-implementation-plan.md` — secondary
  device route refactor implementation record for ITE 8258 chassis
- `secondary-device-route-refactor-plan.md` — original virtual-route proposal;
  retained for history, with remaining UI/profile work superseded by the active plan

### Archived campaign docs

- `2026-04-19/architecture-and-maintainability-improvement-plan.md`
- `2026-04-19/package-and-gui-boundary-refactor-anchor-plan.md`
- `2026-04-19/refactor-campaign-progress.md`
- `../B-backend-guides/ite8258/ite8258-chassis-correction-plan.md`
- `2026-04-01/diagnostics-discovery-roadmap.md`
- `2026-03-29/V1_RELEASE_SPRINT.md`

## See also

- `docs/B-backend-guides/ite8258/ite8258-chassis-backend-plan.md` — backend
  implementation plan for ITE 8258 chassis
- `docs/P-power-management/power-mode-verification-refactor-plan.md` — power
  mode verification refactor
- `docs/U-gui/physical-slot-id-roadmap.md` — physical slot ID roadmap
