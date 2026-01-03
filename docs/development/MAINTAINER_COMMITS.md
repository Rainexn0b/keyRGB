# Maintainer workflow (commits & releases)

This document is for the repo owner/maintainers.

## Day-to-day workflow

- Keep `main` green.
- For changes beyond trivial docs edits:
  - Create a branch
  - Open a PR
  - Merge via GitHub

Recommended branch naming:
- `fix/<topic>`
- `feature/<topic>`
- `docs/<topic>`

## Local sanity checks

```bash
python3 -m compileall -q src
pytest -q -o addopts=
```

## Versioning

- Update the version in `pyproject.toml` when you want a release tag.
- Tag releases like `vX.Y.Z`.

## Pushing tags safely

Avoid using `git push --tags` unless you are 100% sure your local tag list is clean.

Recommended flow:

```bash
# Create the release tag (example)
git tag -a v0.4.0 -m "v0.4.0"

# Push just the tag you intended
git push origin v0.4.0
```

If you ever see “wrong” tags show up on GitHub, it’s usually because those tags still exist locally and got pushed later.
You can list and delete stray tags locally:

```bash
git tag -l | sort
git tag -d <bad-tag>
```

Also check whether your git is configured to push tags automatically:

```bash
git config --get push.followTags
git config --global --get push.followTags
```

## Autostart / installer expectations

- `install.sh`:
  - Installs the vendored `ite8291r3-ctl` package.
  - Installs KeyRGB itself (`pip install --user -e .`) so the `keyrgb` console script exists.
  - Writes a freedesktop autostart entry to `~/.config/autostart/keyrgb.desktop`.

If you change the entrypoints, update both `pyproject.toml` and `install.sh`.

## Handling the `ite8291r3-ctl` dependency

KeyRGB currently vendors a modified copy of `ite8291r3-ctl/` because upstream changes are pending and we need those patches.

Current approach (simple and reliable):
- Keep the modified source under `ite8291r3-ctl/` in this repo.
- `install.sh` installs it via `python3 -m pip install --user ./ite8291r3-ctl`.
- When running from a cloned repo, KeyRGB prefers the vendored copy automatically (unless `KEYRGB_USE_INSTALLED_ITE=1`).

How to update it later:
- If upstream merges the needed PR(s), either:
  - Replace `ite8291r3-ctl/` with the upstream release (and drop local patches), or
  - Maintain a small patch set and rebase it onto upstream.

Avoid these (they tend to break packaging/install for users):
- Depending on an unreleased upstream commit by default.
- Using a Git URL dependency as the only install path (hard for users, and not PyPI-friendly).

If we ever want “single-package” installs (no separate `ite8291r3-ctl` install step), the next step is to vendor the library into KeyRGB’s own Python package namespace and import it from there. That’s a bigger refactor and should be done intentionally.
