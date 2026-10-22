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

Run the local CI-equivalent gate before publishing:

```bash
.venv/bin/python -m buildpython --profile=ci
```

The tag-triggered release workflow builds the AppImage on Ubuntu 22.04 and installs
`zsyncmake` (the `zsync` package). A local `--profile=release` run is optional on
hosts equipped for AppImage builds. If it fails solely because a release-host
dependency such as `zsyncmake` is missing, rely on the release workflow instead;
never ignore code, test, or dependency-audit failures. Buildpython validates the
embedded update information and the `.zsync` sidecar's length, SHA-1, filename,
URL, and block checksum table before release upload.

Then run the safe release flow:

```bash
git add -A
git status --short  # inspect the staged set
git commit -m "Release vX.Y.Z"
git push origin main
# Verify origin/main points at HEAD, its CI quality/runtime jobs passed, and the tag does not exist locally or remotely.
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Only tag after the committed revision is on `origin/main` and its CI passes.
After the tagged release workflow succeeds, download and verify all three
nonempty GitHub Release assets:

- `keyrgb-x86_64.AppImage`
- `keyrgb-x86_64.AppImage.zsync`
- `keyrgb-x86_64.AppImage.sha256`

Run `sha256sum -c keyrgb-x86_64.AppImage.sha256` in the download directory
alongside the AppImage. Do not consider the release complete if any asset is
missing or empty or the checksum fails.

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
