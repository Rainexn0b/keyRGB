# AppImage catalog compatibility — 2026-10-05

## Evidence and root cause

- Catalog PR: <https://github.com/AppImage/appimage.github.io/pull/8815>.
- Failing catalog run: <https://github.com/AppImage/appimage.github.io/actions/runs/36654486062>.
- The catalog tested 0.37.0 on Ubuntu 22.04. Its loader rejected
  `libpython3.12.so.1.0`: `GLIBC_2.38` was unavailable in both `libc` and `libm`.
- The published 0.37.1 artifact reproduces the same failure in an isolated
  Ubuntu 22.04 base rootfs (glibc 2.35). This happens before KeyRGB or udev
  permission checks can execute.
- Release builds used the floating `ubuntu-latest` with Python 3.12. The old
  smoke test only used Ubuntu 24.04 and did not load the GI/indicator backend.
- The indicator bundle omitted `libdbusmenu-glib.so.4`. The GI typelib allowlist
  also omitted transitive namespaces: the stronger desktop probe concretely
  failed with `Typelib file for namespace 'xlib', version '2.0' not found`.

## Changed files

- `.github/workflows/release.yml`: pin Ubuntu 22.04 and Python 3.10 (matching
  Jammy's apt-provided GI extension ABI); explicitly install build tools.
- `buildpython/steps/appimage/compatibility.py`: inspect version needs in every
  bundled ELF and reject requirements above GLIBC_2.35 or unknown GLIBC ABI tags.
  Require a working `readelf`; use its C locale; do not scan arbitrary strings.
- `buildpython/steps/appimage/build.py`: run that check before packaging a real
  AppImage. Staging-only behavior and public helpers remain unchanged.
- `buildpython/steps/appimage/appindicator_bundle.py`: bundle dbusmenu-glib.
- `buildpython/steps/appimage/pygobject_bundle.py`: retain the build environment's
  complete typelib metadata set, including transitive namespace dependencies.
- `buildpython/steps/appimage/smoke.py`: default to 22.04 and 24.04, exercise Tk
  window creation and indicator construction under Xvfb, and call the actual
  `AppRun --diagnostics --no-usb`. Preserve the custom-image override and skip
  reporting. Force X11 only in the test fixture, not in the application.
- `tests/buildpython/test_buildpython_appimage_compatibility_unit.py`: ABI,
  bundling, matrix/override/failure, and launcher smoke regressions.
- `tests/buildpython/test_build_docs_unit.py`: guard release ABI-floor pins.
- `docs/1-buildpython/03-CI.md`: document the portability contract and checks.
- `buildpython/steps/step_defs.py` and `docs/1-buildpython/01.1-Build-steps.md`:
  describe the smoke check's actual minimal/desktop scope.
- `CHANGELOG.md`: record packaging fixes under Unreleased.
- This investigation report.

## Validation ledger

Primary worktree commands:

```bash
.venv/bin/python -m pytest -q -o addopts= \
  tests/buildpython/test_buildpython_appimage_compatibility_unit.py \
  tests/buildpython/test_buildpython_appimage_unit.py \
  tests/buildpython/test_buildpython_appimage_tkinter_unit.py \
  tests/buildpython/test_build_docs_unit.py \
  tests/installer/test_release_input_pins_unit.py
.venv/bin/ruff check buildpython/steps/appimage \
  tests/buildpython/test_buildpython_appimage_compatibility_unit.py \
  tests/buildpython/test_build_docs_unit.py
.venv/bin/ruff format --check buildpython/steps/appimage \
  tests/buildpython/test_buildpython_appimage_compatibility_unit.py \
  tests/buildpython/test_build_docs_unit.py
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --run-steps=19
git diff --check
```

Focused tests: **53 passed**. CI profile: **18/18 checks passed**, **5,111 tests
passed, 1 skipped**. Ruff, formatting, explicit Step 19, and diff checks passed.

Actual portable build (isolated Ubuntu 22.04, distro CPython 3.10.12):

```bash
bwrap --unshare-user --uid 0 --gid 0 \
  --bind /tmp/opencode/keyrgb-appimage-compatibility/ubuntu22 / \
  --proc /proc --dev /dev --chdir /work/keyrgb \
  --setenv HOME /root --setenv LC_ALL C.UTF-8 \
  /work/venv/bin/python -m buildpython --run-steps=14
```

Passed; **111 ELF files**, highest requirement **GLIBC_2.35**. The portable test
artifact is in `ubuntu22/work/keyrgb/dist/` under the investigation directory,
not installed or published. The package version was not bumped.

Docker is unavailable locally. Instead, the **same generated smoke script** was
executed in separate Ubuntu 22.04 and 24.04 base rootfs namespaces:

```bash
.venv/bin/python -c \
  'from buildpython.steps.appimage.smoke import _smoke_script; print(_smoke_script())' \
  > /tmp/opencode/keyrgb-appimage-compatibility/smoke-script.sh
for baseline in 22 24; do
  bwrap --unshare-user --uid 0 --gid 0 --clearenv \
    --bind "/tmp/opencode/keyrgb-appimage-compatibility/smoke$baseline" / \
    --proc /proc --dev /dev \
    --ro-bind /tmp/opencode/keyrgb-appimage-compatibility/ubuntu22/work/keyrgb/dist /dist \
    --ro-bind /tmp/opencode/keyrgb-appimage-compatibility/smoke-script.sh /smoke-script.sh \
    --chdir /work --setenv PATH /usr/sbin:/usr/bin:/sbin:/bin \
    --setenv HOME /root --setenv LC_ALL C.UTF-8 /bin/bash -c \
    'apt-get() { /usr/bin/fakeroot-sysv /usr/bin/apt-get -o APT::Sandbox::User=root "$@"; }; source /smoke-script.sh'
done
```

Both produced `desktop-tray-ok`, `apprun-ok`, and `appimage-smoke-ok`. Neither
test rootfs had system `python3-gi`, `gir1.2-*`, indicator, or dbusmenu packages
installed. Base archives were verified against Canonical's SHA256SUMS.
Namespace setup used fakeroot, mapped the test rootfs's staff/adm groups to gid
0, and preconfigured the unused system-bus launch helper's statoverride to avoid
unmapped ownership errors. These are fixture-only accommodations, not changes
to the host, AppImage, or release workflow. Clearing inherited environment
prevented the developer host's Wayland-only GTK setting from contaminating Xvfb.

An additional default tray launch under Xvfb/session D-Bus survived 15 seconds
(timeout status 124) and logged `KeyRGB tray app started`. It did not prove icon
visibility in a real status-notifier host. A pre-existing `Unknown effect:
rainbow` error was non-fatal on the no-device path; investigate separately.
Missing system D-Bus, Wayland, and accessibility services caused expected
fixture warnings. No host udev changes or hardware writes were performed.

## Boundaries and follow-up

- glibc/loader and GTK/GLib/font rendering remain host desktop components;
  bundling an old GTK/font stack can break newer distributions. This is an
  Ubuntu 22.04 ABI floor, not universal compatibility with older Linux systems.
- The exact GitHub setup-python build and catalog screenshot test remain to be
  exercised in the next release. Do not request `/retest` against unchanged
  0.37.1 assets; publish a new release first when authorized.
- Udev, optional input-device access, and polkit setup are separate privileged
  system integration. No installer behavior changed in this patch.
- Recommended next discussion: an explicit first-run/Settings hardware-access
  setup using bundled, versioned rules and a narrow privileged helper. Never
  run the whole GUI as root or silently download/execute an installer on launch.
