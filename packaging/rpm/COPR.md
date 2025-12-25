# COPR publishing (Fedora)

This repo ships an RPM spec so KeyRGB can be installed via `dnf`.

Important reality check:
- There is no “magic” `sudo dnf install keyrgb` until you publish a repository (COPR is the typical route).
- COPR builds RPMs from an SRPM or a source SCM.

## What you need

- A Fedora account
- A COPR project (e.g. `Rainexn0b/keyrgb`)
- `copr-cli` installed locally, or configured in CI

Install tooling on Fedora:

```bash
sudo dnf install -y copr-cli rpmdevtools rpmlint python3-devel python3-setuptools python3-wheel pyproject-rpm-macros
```

Configure COPR credentials:

1) Go to https://copr.fedorainfracloud.org/api/
2) Download your API token
3) Place it at `~/.config/copr` (this is what `copr-cli` reads)

## Recommended workflow (SRPM upload)

### 1) Build an SRPM

From the repo root:

```bash
bash scripts/copr-build-srpm.sh
```

This generates:
- `~/rpmbuild/SRPMS/keyrgb-<version>-<release>.src.rpm`

### 2) Create a COPR project (once)

In the COPR UI:
- Create a new project
- Select Fedora releases you want to build for (e.g. `fedora-40`, `fedora-41`)

### 3) Trigger a build

```bash
PROJECT=<copr_user>/<copr_project>
SRPM=$(ls -1t ~/rpmbuild/SRPMS/keyrgb-*.src.rpm | head -n 1)

copr-cli build "$PROJECT" "$SRPM"
```

### 4) Users install from COPR

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf copr enable <copr_user>/<copr_project>
sudo dnf install -y keyrgb
```

## Notes / gotchas

- The spec currently bundles the modified `ite8291r3-ctl` module from this repo. COPR usually tolerates this; official Fedora packaging generally prefers separate source RPMs for bundled libraries.
- After installation, the udev rule is installed, but the user may need to replug or reboot for `uaccess` permissions to apply.
- For GUI autostart: Fedora desktops typically prefer XDG autostart. KeyRGB’s `install.sh` sets that up; RPM install does not automatically enable autostart (by design).
