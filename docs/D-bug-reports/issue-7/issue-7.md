# Issue 7: Lenovo Legion Pro 7 16IAX10H (`0x048d:0xc197`) hardware support

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/7

This folder tracks investigation notes, regression reviews, and open validation
for the composite ITE 8258 chassis path (keyboard + logo + neon + vent).

## Status (2026-07-15)

- **Hardware detection / udev / keyboard path:** largely addressed across
  `0.25.x`–`0.28.x` (experimental backend, udev rules, matrix fixes, secondary
  routes).
- **Secondary static + profile editor:** introduced in `0.29.0` / refined in
  `0.29.1`.
- **v0.29.1 regression (mode change → flash → all dark):** dual-seam fix is in
  the working tree (profile coordinator + legacy config-mirror gating).
- **Hardening Phases 1–5 + Phase 8 debug script:** implemented 2026-07-15 —
  desired-scene vs output suspension, optional one-commit `output_transaction`,
  authority helper rename, cross-layer integration test, debug close visibility.
  Focused automated suite is green; **reporter hardware revalidation remains the
  closure gate**. Phase 0/6/7/8 reporter evidence and hidraw descriptor filtering
  are still open.
- **Maintainer review of residual findings:** classified in the hardening plan;
  generic coordinator extraction and product variants remain evidence-triggered.

## Workstream and closure gates

| Workstream | Current state | Closure evidence |
|---|---|---|
| Detection, permissions, sparse keymap | Implemented in earlier releases | Existing issue retests and support bundles |
| Static/profile regression dual-seam fix | Implemented in working tree | Focused + CI validation; reporter c197 retest pending |
| Residual coordinator hardening (P1–5) | Implemented in working tree | Unit + cross-layer integration tests green |
| Shared hidraw interface filtering | Open promotion blocker | Real c195/c197 descriptors plus selector tests |
| Stable Issue #7 closure | Open | Exact artifact, reporter checklist, logs/support bundle for any failure |

## Documents in this folder

| Doc | Contents |
|---|---|
| [`01-second-review-0.29.1-regression-2026-07-15.md`](01-second-review-0.29.1-regression-2026-07-15.md) | Second-reviewer validation of the dual-seam fix: verdict, residual risks, architectural notes, hardware checklist |

## Related docs (outside this folder)

- Composite profile coordination reference: [`docs/1-src/12-composite-profile-coordination.md`](../../1-src/12-composite-profile-coordination.md)
- Residual hardening and validation plan: [`docs/I-implementation-plans/issue-7-composite-profile-hardening-and-validation-plan.md`](../../I-implementation-plans/issue-7-composite-profile-hardening-and-validation-plan.md)
- Backend audit: [`docs/B-backend-audits/06-ite8258-chassis.md`](../../B-backend-audits/06-ite8258-chassis.md)
- Secondary lighting plan: [`docs/I-implementation-plans/secondary-lighting-profile-editor-and-simulation-plan.md`](../../I-implementation-plans/secondary-lighting-profile-editor-and-simulation-plan.md)
- Chassis secondary refactor plan: [`docs/I-implementation-plans/ite8258-chassis-secondary-device-refactor-implementation-plan.md`](../../I-implementation-plans/ite8258-chassis-secondary-device-refactor-implementation-plan.md)
