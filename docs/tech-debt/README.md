# Tech debt (maintainability)

This folder tracks the active maintainability issues called out in the March 2026 codebase review.

Goals:

- Keep the debt visible and scoped to concrete modules.
- Tie each debt item to an observable buildpython signal where possible.
- Make cleanup work easier to slice into small PRs.

Start here:

- [tracking.md](tracking.md): current backlog and priorities.
- [exception-handling-debt.md](exception-handling-debt.md): broad exception debt and failure visibility.
- [tray-runtime-state.md](tray-runtime-state.md): tray state, pollers, and coordination debt.
- [backend-coverage-and-confidence.md](backend-coverage-and-confidence.md): backend test confidence and coverage gaps.
- [backend-shared-usb-layer.md](backend-shared-usb-layer.md): duplicated USB-backend logic.
- [polling-and-config-sync.md](polling-and-config-sync.md): config polling and event-model debt.
- [buildpython-debt-automation.md](buildpython-debt-automation.md): how buildpython can track this work.

Recommended commands:

```bash
.venv/bin/python -m buildpython --profile debt
.venv/bin/python -m buildpython --run-steps=16,17 --continue-on-error
```

Primary report outputs:

- `buildlog/keyrgb/code-hygiene.md`
- `buildlog/keyrgb/code-markers.md`
- `buildlog/keyrgb/file-size-analysis.md`
- `buildlog/keyrgb/loc-check.md`
- `buildlog/keyrgb/architecture-validation.md`
- `buildlog/keyrgb/build-summary.md`

Snapshot metadata:

- Last updated: 2026-03-30
- Review basis: repository inspection, committed coverage artifacts, and existing buildpython debt reports