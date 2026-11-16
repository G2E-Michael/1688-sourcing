#!/usr/bin/env bash
# Install the 1688-supplier-finder skill into DSH and/or WorkBuddy.
#   bash install.sh            # both
#   bash install.sh dsh        # DSH only
#   bash install.sh workbuddy  # WorkBuddy only
#   FORCE=1 bash install.sh    # overwrite existing
set -euo pipefail

SKILL_NAME="1688-supplier-finder"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-both}"
FORCE="${FORCE:-0}"

[ -f "$ROOT/SKILL.md" ] || { echo "SKILL.md not found next to install.sh — run from the cloned repo root" >&2; exit 1; }

copy_skill() {
  local dest="$1" label="$2"
  echo
  echo "== install -> $label"
  if [ -d "$dest" ]; then
    if [ "$FORCE" != "1" ]; then
      echo "   exists: $dest"
      echo "   skipped (set FORCE=1 to overwrite)"
      return 0
    fi
    echo "   replacing existing install"
    rm -rf "$dest"
  fi
  mkdir -p "$dest"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.git' --exclude 'out' --exclude '__pycache__' --exclude '.venv' \
      --exclude '*.pyc' "$ROOT"/ "$dest"/
  else
    (cd "$ROOT" && tar --exclude='./.git' --exclude='./out' --exclude='__pycache__' \
      --exclude='*.pyc' --exclude='./.venv' -cf - .) | (cd "$dest" && tar -xf -)
  fi
  echo "   ok: $dest"
}

check_deps() {
  echo
  echo "== dependencies"
  command -v node >/dev/null 2>&1 && echo "   node      : $(node --version)" || echo "   node      : MISSING (need Node 20+)"
  command -v python3 >/dev/null 2>&1 && echo "   python    : $(python3 --version)" || echo "   python    : MISSING (need Python 3.10+)"
  if [ -d "/Applications/Google Chrome.app" ]; then
    echo "   chrome    : /Applications/Google Chrome.app"
  elif command -v google-chrome >/dev/null 2>&1; then
    echo "   chrome    : $(command -v google-chrome)"
  elif command -v chromium >/dev/null 2>&1; then
    echo "   chrome    : $(command -v chromium)"
  else
    echo "   chrome    : MISSING (the driver uses channel=chrome)"
  fi
  if npm root -g >/dev/null 2>&1 && [ -f "$(npm root -g)/1688-cli/dist/cli.js" ]; then
    echo "   1688-cli  : ok"
  else
    echo "   1688-cli  : MISSING -> npm i -g 1688-cli"
  fi
  if python3 -c "import openpyxl, requests, PIL" >/dev/null 2>&1; then
    echo "   py deps   : openpyxl / requests / Pillow ok"
  else
    echo "   py deps   : MISSING -> python3 -m pip install -r requirements.txt"
  fi
}

case "$TARGET" in
  dsh)       copy_skill "$HOME/.dsh/skills/$SKILL_NAME" "DSH" ;;
  workbuddy) copy_skill "$HOME/.workbuddy/skills/$SKILL_NAME" "WorkBuddy" ;;
  both)      copy_skill "$HOME/.dsh/skills/$SKILL_NAME" "DSH"
             copy_skill "$HOME/.workbuddy/skills/$SKILL_NAME" "WorkBuddy" ;;
  *) echo "usage: bash install.sh [dsh|workbuddy|both]" >&2; exit 1 ;;
esac

check_deps

echo
echo "== next steps"
echo "   1) one-time login :  npx 1688 login --headed"
echo "   2) self check     :  python3 run.py check"
echo "   3) try it         :  python3 run.py keyword \"硅胶折叠水杯\" --max 12 --top 6 --enrich 3"
echo "   4) reload client  :  DSH refresh page / WorkBuddy restart or refresh skill list"
echo
