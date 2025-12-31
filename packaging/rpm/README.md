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

`Source0:` in the spec points to the GitHub tag tarball (`v<version>`), so `rpmbuild` needs you to fetch sources into `~/rpmbuild/SOURCES/`.

If you want to build from your local working tree instead of the tag tarball, you can still generate a local `Source0` tarball and place it in `~/rpmbuild/SOURCES/` (see note below).

Then build an RPM:

```bash
# Creates ~/rpmbuild/{SOURCES,SPECS,...} if missing
rpmdev-setuptree

# Copy Patch1 into rpmbuild SOURCES
cp -f packaging/rpm/ite8291r3-ctl-wootbook-support.patch ~/rpmbuild/SOURCES/

# Fetch remote sources (Source0 + Source1) into rpmbuild SOURCES
# (required because rpmbuild does not automatically download remote sources)
spectool -g -R packaging/rpm/keyrgb.spec -C ~/rpmbuild/SOURCES/

# Copy the spec into rpmbuild SPECS
cp -f packaging/rpm/keyrgb.spec ~/rpmbuild/SPECS/

# Build
rpmbuild -ba ~/rpmbuild/SPECS/keyrgb.spec
```

Note (build from local HEAD instead of the GitHub tag tarball):

```bash
VERSION=0.5.1
git archive --format=tar.gz --prefix=keyRGB-$VERSION/ -o keyrgb-$VERSION.tar.gz HEAD
cp -f keyrgb-$VERSION.tar.gz ~/rpmbuild/SOURCES/
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
- Fedora has guidelines around bundling. This spec bundles upstream `ite8291r3-ctl` as `Source1` and applies a tiny patch for Wootbook (`0x600B`).
- For official Fedora packaging you would typically package `ite8291r3-ctl` separately.
