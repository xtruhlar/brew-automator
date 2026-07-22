#!/usr/bin/env bash
# Cut a new release: bump __version__, commit, tag, push, and publish a
# GitHub release. The Homebrew tap formula then gets bumped automatically
# by .github/workflows/bump-homebrew-formula.yml.
#
# Usage: scripts/release.sh 0.9.0
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>  (e.g. $0 0.9.0)" >&2
    exit 1
fi

VERSION="$1"

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Version must be in X.Y.Z format, got: $VERSION" >&2
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ -n "$(git status --porcelain)" ]; then
    echo "Working tree is not clean. Commit or stash changes first." >&2
    exit 1
fi

INIT_FILE="brew_automator/__init__.py"
echo "__version__ = \"$VERSION\"" > "$INIT_FILE"

git add "$INIT_FILE"
git commit -m "chore: release v$VERSION"
git tag -a "v$VERSION" -m "v$VERSION"
git push origin main
git push origin "v$VERSION"
gh release create "v$VERSION" --title "v$VERSION" --generate-notes

echo "Released v$VERSION. The Homebrew tap formula will update automatically via CI."
