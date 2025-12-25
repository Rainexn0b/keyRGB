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
TAR="$ROOT/${NAME}-${VERSION}.tar.gz"

echo "Building SRPM for ${NAME} ${VERSION}"

# Create Source0 tarball matching the spec
rm -f "$TAR"
(
  cd "$ROOT"
  git archive --format=tar.gz --prefix="${NAME}-${VERSION}/" -o "$TAR" HEAD
)

rpmdev-setuptree >/dev/null

cp -f "$TAR" "$HOME/rpmbuild/SOURCES/"
cp -f "$SPEC" "$HOME/rpmbuild/SPECS/"

rpmbuild -bs "$HOME/rpmbuild/SPECS/keyrgb.spec"

echo
echo "SRPM created:"
ls -1t "$HOME/rpmbuild/SRPMS/${NAME}-"*.src.rpm | head -n 1
