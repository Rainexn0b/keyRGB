# Fedora / RPM packaging (dnf install)

This repo includes an RPM spec so you can install KeyRGB via `dnf`.

Two options:

1) Local install (build RPM on your machine)
2) COPR (publish a repo so users can `dnf install keyrgb`)

## 1) Local build + install

Install build tools:

```bash
sudo dnf install -y rpmdevtools rpmlint python3-devel python3-setuptools python3-wheel pyproject-rpm-macros
```

From the repo root, create the source tarball (matches `Source0:` in the spec):

```bash
VERSION=1.0.0
git archive --format=tar.gz --prefix=keyrgb-$VERSION/ -o keyrgb-$VERSION.tar.gz HEAD
```

Then build an RPM:

```bash
# Creates ~/rpmbuild/{SOURCES,SPECS,...} if missing
rpmdev-setuptree

# Copy Source0 into rpmbuild SOURCES
cp -f keyrgb-$VERSION.tar.gz ~/rpmbuild/SOURCES/

# Copy the spec into rpmbuild SPECS
cp -f packaging/rpm/keyrgb.spec ~/rpmbuild/SPECS/

# Build
rpmbuild -ba ~/rpmbuild/SPECS/keyrgb.spec
```

Install the resulting RPM:

```bash
sudo dnf install -y ~/rpmbuild/RPMS/noarch/keyrgb-*.rpm
```

After install:

- Start: `keyrgb`
- Enable udev rule: replug device or reboot (or `sudo udevadm control --reload && sudo udevadm trigger`)

## 2) COPR (for real `sudo dnf install keyrgb`)

Once you publish this spec in COPR, users can do:

```bash
sudo dnf install -y dnf-plugins-core
sudo dnf copr enable <you>/<project>
sudo dnf install -y keyrgb
```

Notes:
- Fedora has guidelines around bundling vendored code. This spec installs the vendored `ite8291r3-ctl` module from this repo.
- For official Fedora packaging you would typically package `ite8291r3-ctl` separately.
