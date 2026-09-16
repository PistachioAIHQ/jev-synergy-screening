#!/usr/bin/env bash
# Run on Pranay's Mac after copying the box checkout (or clone + cherry-pick).
set -euo pipefail
ROOT="${1:-$HOME/Documents/projects/jev-synergy-screening}"
mkdir -p "$(dirname "$ROOT")"
if [[ ! -d "$ROOT/.git" ]]; then
  gh repo clone PistachioAIHQ/jev-synergy-screening "$ROOT"
fi
cd "$ROOT"
# If this tree was rsynced from the box:
git status
git push -u origin main
echo "Pushed. Open https://github.com/PistachioAIHQ/jev-synergy-screening"
