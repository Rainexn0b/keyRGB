# Release procedure

Update the version and changelog first:

- `pyproject.toml` -> `[project].version`
- `CHANGELOG.md` -> add the matching release heading and notes

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
