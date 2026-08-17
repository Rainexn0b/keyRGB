# AppImage notes

- `dist/keyrgb-x86_64.AppImage` is the release artifact.
- AppImage smoke tests skip locally when Docker is unavailable.
- Release builds pin `appimagetool` to a versioned upstream release and verify
  its SHA-256 before use (`buildpython/steps/appimage/build.py`). The old
  `AppImageKit/continuous` URL is intentionally not used.
- GitHub Actions workflows pin third-party actions to commit SHAs.
- Installer AppImage downloads verify against the published `.sha256` sidecar.
  Set `KEYRGB_REQUIRE_CHECKSUM=1` to fail closed when the sidecar or
  `sha256sum` is unavailable (default remains best-effort for older releases).
