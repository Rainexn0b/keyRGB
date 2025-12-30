#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="$ROOT/packaging/rpm/keyrgb.spec"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi

if [ ! -f "$SPEC" ]; then
  echo "Missing spec: $SPEC" >&2
  exit 1
fi

# Read version from pyproject.toml
VERSION="$(
  python3 - <<'PY'
import re
from pathlib import Path

path = Path('pyproject.toml')
text = path.read_text(encoding='utf-8')

# Prefer tomllib when available
try:
    import tomllib  # py3.11+
    data = tomllib.loads(text)
    print(data['project']['version'])
except Exception:
    m = re.search(r"^version\s*=\s*\"([^\"]+)\"\s*$", text, flags=re.M)
    if not m:
        raise SystemExit('Could not read project.version from pyproject.toml')
    print(m.group(1))
PY
)"

NAME="keyrgb"
SOURCE0_NAME="v${VERSION}.tar.gz"
SOURCE1_NAME="master.tar.gz"
PATCH1_NAME="ite8291r3-ctl-wootbook-support.patch"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

TAR="$TMPDIR/${SOURCE0_NAME}"

echo "Building SRPM for ${NAME} ${VERSION}"

# Create Source0 tarball matching the spec
(
  cd "$ROOT"
  # Spec expects: Source0 .../v<version>.tar.gz and %autosetup -n keyRGB-<version>
  git archive --format=tar.gz --prefix="keyRGB-${VERSION}/" -o "$TAR" HEAD
)

rpmdev-setuptree >/dev/null

cp -f "$TAR" "$HOME/rpmbuild/SOURCES/"
cp -f "$ROOT/packaging/rpm/$PATCH1_NAME" "$HOME/rpmbuild/SOURCES/"
cp -f "$SPEC" "$HOME/rpmbuild/SPECS/"

# Source1 is a remote tarball in the spec; rpmbuild -bs requires it present.
if [ ! -f "$HOME/rpmbuild/SOURCES/$SOURCE1_NAME" ]; then
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$HOME/rpmbuild/SOURCES/$SOURCE1_NAME" \
      "https://github.com/pobrn/ite8291r3-ctl/archive/refs/heads/master.tar.gz"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$HOME/rpmbuild/SOURCES/$SOURCE1_NAME" \
      "https://github.com/pobrn/ite8291r3-ctl/archive/refs/heads/master.tar.gz"
  elif command -v spectool >/dev/null 2>&1; then
    # Fallback: spectool fetches *all* remote sources and will fail if the
    # Source0 GitHub tag tarball doesn't exist yet.
    spectool -g -R "$SPEC" -C "$HOME/rpmbuild/SOURCES/" >/dev/null
  else
    echo "Missing $SOURCE1_NAME and neither spectool/curl/wget is available" >&2
    exit 1
  fi
fi

rpmbuild -bs "$HOME/rpmbuild/SPECS/keyrgb.spec"

echo
echo "SRPM created:"
ls -1t "$HOME/rpmbuild/SRPMS/${NAME}-"*.src.rpm | head -n 1
