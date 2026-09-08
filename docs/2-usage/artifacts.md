# Artifacts

## AppImage

Release binary: `dist/keyrgb-x86_64.AppImage`.

- Smoke tests skip locally without Docker.
- Builds pin `appimagetool` to a versioned SHA-256 (`buildpython/steps/appimage/build.py`).
- Installer downloads verify the published `.sha256` sidecar and fail closed by
  default: a missing `sha256sum` tool, missing sidecar, empty/malformed
  sidecar, temporary-file creation failure, hash-tool failure, or hash
  mismatch removes the downloaded AppImage
  and aborts with an integrity-verification error (distinct from a plain
  download failure). This applies to current releases (`v0.23.4` and later),
  prerelease variants at/after that version, mutable refs such as `main`, and
  any empty/unknown/non-semver ref.
- Only explicit installs of historical tags before `v0.23.4` (which predate
  sidecars) may continue with a warning when the sidecar or `sha256sum` is
  unavailable. A historical sidecar that exists but is empty, malformed, or
  mismatched still fails closed.
- Set `KEYRGB_REQUIRE_CHECKSUM=1` (or `true`/`yes`/`on`) to force strict
  verification even for historical tags. A false/unset value never weakens
  verification of current or unknown tags.

## Python package

```bash
.venv/bin/python -m pip install -U build
.venv/bin/python -m build
```

Wheels must include nested `keyrgb/core/resources/` JSON. CI and
`tests/core/resources/test_packaged_resources_unit.py` smoke-install the wheel.
