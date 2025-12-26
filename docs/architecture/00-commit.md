Fix: Mark pystray as optional in import scan

- Added pystray to OPTIONAL_TOPLEVEL in buildpython/steps/step_import_scan.py.
- This prevents build failures in headless CI environments where pystray cannot be imported due to missing X11 display.
