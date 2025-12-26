Fix: Correct vendored dependency path resolution

- Updated path resolution logic in src/legacy/effects.py, src/gui/tray.py, and src/gui/uniform.py to correctly locate the vendored ite8291r3-ctl library relative to the new project structure.
- This fixes Import Validation failures in CI where the vendored library was not being found.
