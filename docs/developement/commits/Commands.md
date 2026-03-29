# KeyRGB Commands

This is a quick reference for common local workflows in the repository.

## Local Environment

```bash
python3 -m venv .venv
```

If you are on a Linux desktop that needs tray support, make sure `gi` is available to the venv as described in [docs/venv/setup.md](../venv/setup.md).

Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e '.[qt,dev]'
```

## Build Runner / Gates

```bash
.venv/bin/python -m buildpython --list-profiles
.venv/bin/python -m buildpython --list-steps
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --profile=full --with-black
.venv/bin/python -m buildpython --profile=full --with-black --continue-on-error
.venv/bin/python -m buildpython --profile=ci --with-appimage
.venv/bin/python -m buildpython --profile=release
```

## Step-Specific Runs

```bash
.venv/bin/python -m buildpython --run-steps=1,2
.venv/bin/python -m buildpython --run-steps="Ruff,Ruff Format,Black"
.venv/bin/python -m buildpython --run-steps="Import Validation,Import Scan,Pip Check"
.venv/bin/python -m buildpython --run-steps=14,15
```

## Commit Procedure

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

## Release Procedure

Update the version and changelog first:

- `pyproject.toml` -> `[project].version`
- `CHANGELOG.md` -> add release heading / notes

Then run:

```bash
.venv/bin/python -m buildpython --profile=release
git add -A
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push --follow-tags
```

## Optional Package Build

```bash
.venv/bin/python -m pip install -U build
.venv/bin/python -m build
```

## Logs / Summaries

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

## Runtime Debug

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

## Hardware Tests

Hardware tests are opt-in only:

```bash
KEYRGB_HW_TESTS=1 .venv/bin/python -m pytest -q -o addopts=
```

## AppImage Notes

- `dist/keyrgb-x86_64.AppImage` is the artifact.
- AppImage smoke tests skip locally when Docker is unavailable.

## Rollback

This is destructive.

```bash
git fetch origin
git reset --hard origin/main
```

## Brightness Logging

```bash
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb >> ./keyrgb-brightness.log 2>&1
```