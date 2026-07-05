# Backend coverage and hardware confidence debt

## Problem

The project has a large test suite, but the least portable and most hardware-sensitive areas still have weak machine confidence. That matters because regressions in backend probing, permission handling, and sysfs or hidraw writes are exactly the failures that users cannot easily debug.

## Evidence

- There are 120 test modules under `tests`.
- The committed coverage artifact at `htmlcov/index.html` reports 5% total coverage.
- Coverage gaps called out directly in the report include:
  - `src/core/backends/asusctl/backend.py`: 0%
  - `src/core/backends/asusctl/device.py`: 0%
  - `src/core/backends/sysfs/backend.py`: 0%
  - `src/core/backends/sysfs/device.py`: 0%
  - `src/core/backends/ite8297/backend.py`: 0%
  - `src/core/backends/ite8297/device.py`: 0%
  - `src/core/power/power_management/manager.py`: 0%

Note: the committed coverage artifact may be stale, but it is still the machine-readable signal currently checked into the repo.

## Risks

- Refactors in backend code can ship with only indirect coverage.
- Backend selection may remain reliable while actual device control paths drift.
- Experimental backends are harder to promote safely.
- Support burden rises because diagnostics improve faster than verified behavior.

## Desired end state

- Contract tests for every backend:
  - probe
  - capabilities
  - device acquisition
  - permission-denied behavior
  - representative color and brightness writes
- Fixture-driven fake sysfs and fake hidraw coverage.
- Optional hardware smoke tests remain opt-in, but non-hardware coverage becomes strong enough for routine refactors.

## Suggested slices

1. Add fake sysfs fixture coverage for `src/core/backends/sysfs/`.
2. Add fake hidraw or protocol-level tests for `src/core/backends/ite8297/`.
3. Expand ASUS coverage around subprocess and capability behavior in `src/core/backends/asusctl/`.
4. Add focused tests for `src/core/power/power_management/manager.py` with mocked platform inputs.

## Buildpython hooks

- Existing signals:
  - Pytest step 2
  - Architecture Validation step 17
- Current gap:
  - buildpython does not currently treat coverage as a debt signal; the pytest step intentionally runs with `-o addopts=` and therefore does not produce the configured coverage reports.
- Useful next increment:
  - Add a coverage-report step that writes `coverage-summary.json` and fails only on regression against a checked-in baseline.