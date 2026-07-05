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

Then run the safe release flow:

```bash
.venv/bin/python -m buildpython --profile=release
git add -A
git commit -m "Release vX.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

Release notes:

- Package and changelog versions use `X.Y.Z` without a leading `v`.
- Git tags must use `vX.Y.Z`.
- Never use `git push --tags` for KeyRGB releases.
