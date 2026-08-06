#!/usr/bin/env bash
# Cut a new release: bump __version__, commit, tag, push, and publish a
# GitHub release. The Homebrew tap formula then gets bumped automatically
# by .github/workflows/bump-homebrew-formula.yml.
#
# Usage: scripts/release.sh 0.9.0 ["Short summary of what's in this release"]
# The optional summary is prepended above the auto-generated commit changelog.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 <version> [\"summary\"]  (e.g. $0 0.9.0 \"Add settings command\")" >&2
    exit 1
fi

VERSION="$1"
SUMMARY="${2:-}"

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

if [ -n "$SUMMARY" ]; then
    gh release create "v$VERSION" --title "v$VERSION" --notes "$SUMMARY" --generate-notes
else
    gh release create "v$VERSION" --title "v$VERSION" --generate-notes
fi

echo "Released v$VERSION. The Homebrew tap formula will update automatically via CI."
