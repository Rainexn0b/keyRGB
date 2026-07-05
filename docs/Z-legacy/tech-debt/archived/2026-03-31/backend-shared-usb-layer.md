# Shared USB backend layer debt

## Problem

KeyRGB has several hardware backends with similar responsibilities, especially around USB-style probe logic, capability shaping, and error handling. The abstractions are good at the protocol boundary, but there is still duplicated behavior one layer above that.

## Evidence

- Relevant backend modules:
  - `src/core/backends/ite8291r3/backend.py`
  - `src/core/backends/ite8910/backend.py`
  - `src/core/backends/ite8297/backend.py`
- Related shared concepts already exist in parallel but not yet as a common service:
  - probe confidence
  - permission handling
  - backend capability exposure
  - device selection and known-good identifiers

## Risks

- New backend work repeats the same glue logic.
- Fixes to probe or permission behavior have to be copied across backends.
- Backend capability semantics can drift over time.

## Desired end state

- A small shared layer for common USB-backend responsibilities, while leaving protocol and device specifics in backend-local modules.
- Shared helpers for:
  - probe and confidence result construction
  - known identifier matching
  - permission-denied normalization
  - capability metadata helpers where the policy is truly common

## Suggested slices

1. Extract the smallest truly shared helpers into a `usb_common` style module.
2. Keep protocol encoding and hardware write semantics backend-local.
3. Add contract tests around the shared layer before migrating the backends to it.

## Buildpython hooks

- Existing signals:
  - File Size and LOC Check will show whether backend files are shrinking or continuing to grow.
  - Architecture Validation can protect the final boundary once a shared layer exists.
- Useful next increment:
  - Add an architecture rule that keeps protocol-specific modules from reaching back into tray or GUI code as the shared layer is introduced.