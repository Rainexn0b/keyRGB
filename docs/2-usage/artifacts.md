# Artifacts

## AppImage

Release binary: `dist/keyrgb-x86_64.AppImage`.

- Smoke tests skip locally without Docker.
- Builds pin `appimagetool` to a versioned SHA-256 (`buildpython/steps/appimage/build.py`).
- Installer downloads verify the published `.sha256` sidecar. Set
  `KEYRGB_REQUIRE_CHECKSUM=1` to fail closed when the sidecar is missing.

## Python package

```bash
.venv/bin/python -m pip install -U build
.venv/bin/python -m build
```

Wheels must include nested `keyrgb/core/resources/` JSON. CI and
`tests/core/resources/test_packaged_resources_unit.py` smoke-install the wheel.
