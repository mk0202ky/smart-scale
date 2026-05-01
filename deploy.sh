#!/bin/bash
# Smart Scale deploy — stage everything, commit, push to main (auto-deploys to GitHub Pages)
# Usage: ./deploy.sh ["commit message"]

set -e
cd "$(dirname "$0")"

git add -A
if git diff --cached --quiet; then
  echo "No changes to commit. Pushing any unpushed commits..."
else
  git commit -m "${1:-deploy}"
fi
git push origin main
echo "Deployed → https://mk0202ky.github.io/smart-scale/"
