# KeyRGB Commands

This is the organized quick reference for common local workflows in the repository.

## Local environment

Create the venv:

```bash
python3 -m venv .venv
```

Tray-capable Linux setups usually also need `gi` exposed to the venv. See `docs/venv/setup.md`.

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e '.[qt,dev]'
```

## Build runner / gates

```bash
.venv/bin/python -m buildpython --list-profiles
.venv/bin/python -m buildpython --list-steps
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m buildpython --profile=full --with-black --continue-on-error
.venv/bin/python -m buildpython --profile=ci --with-appimage
.venv/bin/python -m buildpython --profile=release
```

## Step-specific runs

```bash
.venv/bin/python -m buildpython --run-steps=1,2
.venv/bin/python -m buildpython --run-steps="Ruff,Ruff Format,Black"
.venv/bin/python -m buildpython --run-steps="Import Validation,Import Scan,Pip Check"
.venv/bin/python -m buildpython --run-steps=14,15
```

## Commit procedure

Single-line flow:

```bash
.venv/bin/python -m buildpython --profile=full --with-black
git add .
git commit -m "comment"
git push
```

Detailed flow:

```bash
.venv/bin/python -m buildpython --profile=full --with-black --continue-on-error
git add -p
git commit
git push
```

## Release procedure

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

## Optional package build

```bash
.venv/bin/python -m pip install -U build
.venv/bin/python -m build
```

## Logs / summaries

```bash
cat buildlog/keyrgb/build-summary.md
ls buildlog/keyrgb
```

Common step logs:

- `buildlog/keyrgb/step-03-ruff.log`
- `buildlog/keyrgb/step-07-ruff-format.log`
- `buildlog/keyrgb/step-11-black.log`
- `buildlog/keyrgb/step-14-appimage.log`
- `buildlog/keyrgb/step-15-appimage-smoke.log`

## Runtime debug

```bash
KEYRGB_DEBUG=1 ./keyrgb
KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
```

## Fixes

```bash
.venv/bin/python -m ruff check src buildpython --fix
.venv/bin/python -m ruff format src buildpython
.venv/bin/python -m black src buildpython
.venv/bin/python -m pytest -q -o addopts=
.venv/bin/python -m pip check
```

## Hardware tests

Hardware tests are opt-in only:

```bash
KEYRGB_HW_TESTS=1 .venv/bin/python -m pytest -q -o addopts=
```

## AppImage notes

- `dist/keyrgb-x86_64.AppImage` is the release artifact.
- AppImage smoke tests skip locally when Docker is unavailable.

## Brightness logging

```bash
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb >> ./keyrgb-brightness.log 2>&1
```