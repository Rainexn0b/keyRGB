# Release procedure

Prepare the release metadata first:

```bash
./scripts/release/version.sh X.Y.Z
```

Alternative (without wrapper):

```bash
.venv/bin/python scripts/release/bump_version.py X.Y.Z
```

That command updates all manual release metadata:

- `pyproject.toml` -> `[project].version`
- `CHANGELOG.md` -> adds `## X.Y.Z (YYYY-MM-DD)` right below `## Unreleased`
- `install.sh` -> updates `KEYRGB_BOOTSTRAP_REF` and default release examples
- `uninstall.sh` -> updates `KEYRGB_BOOTSTRAP_REF`

Then add release notes under the new changelog heading.

Then verify the supply-chain audit locally:

```bash
.venv/bin/python scripts/dependency_audit.py --project-dir .
```

Exit semantics: 0 clean, 1 findings, 2 tool/advisory/resolution failure. It audits
runtime requirements declared in pyproject rather than arbitrary ambient packages.

Then run the safe release flow:

AppImage builds require `zsyncmake` (the `zsync` package on Debian/Ubuntu).
Buildpython validates the embedded update information and the `.zsync` sidecar's
length, SHA-1, filename, URL, and block checksum table before release upload.

```bash
.venv/bin/python -m buildpython --profile=release
git add -A
git commit -m "Release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

After the release workflow succeeds, verify that the GitHub Release contains all
three nonempty assets:

- `keyrgb-x86_64.AppImage`
- `keyrgb-x86_64.AppImage.zsync`
- `keyrgb-x86_64.AppImage.sha256`

The embedded update information is
`gh-releases-zsync|Rainexn0b|keyRGB|latest|keyrgb-x86_64.AppImage.zsync`.
It enables opt-in delta updates with external AppImageUpdate to the latest stable
release only; it is not a pinned-version or prerelease channel. No updater,
automatic update checks, or update-related network access are bundled in KeyRGB.
The installer's `--update-appimage` flow is unchanged.

Release notes:

- Package and changelog versions use `X.Y.Z` without a leading `v`.
- Git tags must use `vX.Y.Z`.
- Never use `git push --tags` for KeyRGB releases.
