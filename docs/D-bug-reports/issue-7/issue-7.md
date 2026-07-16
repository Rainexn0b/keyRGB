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

## Status update (2026-07-16)

- **Reporter confirmation (v0.29.2):** the reporter confirmed "0.29.2 is working
  well" and closed the GitHub issue. This closes the **primary regression** —
  the v0.29.1 mode-change → flash → all-dark defect is resolved on the affected
  83F5 hardware. It is a regression-closure signal, not a structured per-surface
  validation.
- **Backend tier:** remains `EXPERIMENTAL`. The confirmation does not meet the
  promotion bar; the missing gate is the structured Phase 8 reporter checklist
  (per-surface pass/fail), not generic "hardware validation."
- **Phase 6 reframing:** the v0.28.2 support bundle shows the c197 controller
  exposes **exactly one** hidraw node (`hidraw3`); the two other `048d` nodes
  are the companion `c193` device. The multi-interface selection ambiguity that
  Phase 6 guards against does not exist on this hardware, so Phase 6 is
  **lower urgency than the hardening plan implied.** Additionally, the support
  bundle's descriptor read for `hidraw3` failed with
  `report_descriptor_error: [Errno 22] Invalid argument`, so a plain bundle
  re-capture will not produce the descriptor; the read path needs a look first
  (or a `usbhid-dump` capture instead). The c195 descriptor half of Phase 6
  cannot come from this reporter (different device family they do not own).

## Workstream and closure gates

| Workstream | Current state | Closure evidence |
|---|---|---|
| Detection, permissions, sparse keymap | Implemented in earlier releases | Existing issue retests and support bundles |
| Static/profile regression dual-seam fix | Implemented in working tree | Focused + CI validation; **reporter confirmed v0.29.2 working (2026-07-16), regression closed** |
| Residual coordinator hardening (P1–5) | Implemented in working tree | Unit + cross-layer integration tests green |
| Shared hidraw interface filtering | **Demoted:** no selection ambiguity on real c197 hardware (single hidraw node) | Revisit only if a multi-interface c197 unit appears, or bundle with c195 when a c195 reporter surfaces |
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
