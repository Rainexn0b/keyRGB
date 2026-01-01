# Rust considerations for KeyRGB (rewrite vs incremental)

Date: 2025-12-30

This document summarizes whether rewriting KeyRGB in Rust would make sense, based on the current codebase and the project’s roadmap (adding support for more Tongfang-branded keyboards).

## Executive summary

- A full rewrite in Rust is **not recommended** today if there are **no current pain points** and the app is working reliably.
- The highest-value work for “more Tongfang keyboards” is improving **backend selection, probing, quirks, and diagnostics**—which is mostly about device knowledge and safe fallback behavior, not CPU performance.
- If Rust becomes desirable later, the best leverage is usually **Rust for the hardware layer only** (daemon / helper / library), while keeping the UI in Python.

## Current architecture (relevant to the decision)

- **Tray app**: Python `pystray` entrypoint `keyrgb = src.tray.entrypoint:main`, launching the implementation in `src/tray/application.py`.
- **UI callbacks**: Menu actions call into effect/brightness/speed handlers (e.g. `src/tray/lighting_controller.py`).
- **Hardware state polling**: Background polling thread reads brightness/off state roughly every 2 seconds and refreshes the UI (see `src/tray/hardware_polling.py`). This is I/O bound and already defensive about disconnects.
- **Per-key/calibration/settings**: Implemented as Python GUIs with optional `PyQt6`.
- **Backend selection direction**: The README and code indicate a move toward capability-driven, multi-backend behavior (`KEYRGB_BACKEND`, selection via `src.core.backends.registry.select_backend`).
- **Diagnostics**: `keyrgb-diagnostics` is a major scaling tool: it collects read-only system + backend probe snapshots and is designed to support hardware issue triage without local access.

## What Rust would *actually* improve

### Potential benefits

- **Packaging / distribution**
  - A Rust binary can be simpler to ship than Python + GUI toolkit + runtime dependencies.
  - This is most compelling if you target non-Fedora distros or want fewer “works on my machine” dependency issues.

- **Low-level hardware layer ergonomics**
  - If future hardware support requires more complex USB/HID interactions, Rust can be pleasant for that layer.

- **Service/daemon architecture**
  - If you want a single “owner” of the device (to avoid conflicts with other tools) and want stable APIs (e.g., DBus), a Rust daemon is a good fit.

### Things Rust will not automatically fix

- **Cross-desktop tray integration**
  - Linux tray behavior differs across desktops; `pystray` already abstracts some of the pain.
  - In Rust, you may end up spending time on desktop quirks rather than keyboard support.

- **Velocity and stability**
  - Rewrites tend to reintroduce bugs and regress edge-case behavior. This codebase already follows “best effort; don’t crash the tray” patterns.

- **User-visible improvements**
  - If the current app is already stable and responsive, users may not perceive meaningful benefits from a language rewrite.

## Why a full rewrite is low ROI for “more Tongfang keyboards”

Supporting more Tongfang chassis/revisions generally requires:

- Better **device identification** (DMI strings, USB IDs, sysfs LED nodes).
- Better **probing and explainability** (why a backend matched or didn’t).
- A **quirks system** (per-model overrides for matrix dimensions, init sequences, “off/brightness semantics”, etc.).
- A robust **diagnostics → reproduction → fix** loop.

These are primarily domain problems and architectural boundary problems, not performance problems.

## Recommended path: keep Python, strengthen backends

If the goal is to scale keyboard support while minimizing risk, focus on:

1. **Backend boundaries & capabilities**
   - Keep tray/UI fully capability-driven so adding a backend doesn’t require UI changes.
   - Ensure backends expose a stable “capabilities” snapshot and clear failure states.

2. **Probe → match → quirks pipeline**
   - Centralize identification into: (a) probe signals, (b) match rules, (c) quirks application.
   - Prefer data-driven rules where possible (tables / JSON) rather than scattered conditionals.

3. **Diagnostics-first support flow**
   - Make `keyrgb-diagnostics` output “support-ready” (matched backend, rejection reasons, identifiers, permissions hints).
   - Add regression tests against stored sample diagnostics snapshots (anonymized) to prevent breaking previously supported models.

4. **Failure isolation**
   - Preserve the “tray must never crash” rule.
   - Treat device disconnects and permissions issues as expected runtime states.

## If you still want Rust: an incremental approach

If you want to benefit from Rust without a risky rewrite, choose one of these patterns:

### Option A: Rust daemon + DBus API (recommended “Rust path”)

- Rust process owns hardware access and applies effects.
- Python tray and GUIs become DBus clients.
- Benefits: clear separation, easier concurrency, stable API boundary, potential to run as a system/user service.
- Costs: DBus API design, systemd integration, packaging complexity.

### Option B: Rust CLI helper (simpler than DBus)

- Rust binary performs low-level device actions.
- Python calls it for operations or state queries.
- Benefits: simpler than DBus.
- Costs: less efficient for high-frequency updates, error handling across process boundary.

### Option C: Rust library via PyO3

- Rust compiled extension module exposes a Python API.
- Benefits: tight integration and performance.
- Costs: build toolchain complexity, binary wheels per distro/arch considerations.

## Decision rule

A Rust rewrite becomes worth reconsidering if at least one of these becomes true:

- Packaging/support burden from Python/Qt dependencies becomes a major time sink.
- You want a daemonized architecture (single device owner, DBus, multi-client control).
- You need significantly higher-frequency per-key rendering/effects where Python overhead is measurable.

Otherwise, the fastest way to “support more Tongfang keyboards” is to keep the current app and invest in the backend/probing/quirks/diagnostics pipeline.
