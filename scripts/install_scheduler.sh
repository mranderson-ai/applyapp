#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_NAME="com.applyapp.daily.plist"
DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
PYTHON="$ROOT/.venv/bin/python"
LABEL="com.applyapp.daily"

if [[ ! -x "$PYTHON" ]]; then
  echo "Create the venv first: python3 -m venv .venv && .venv/bin/pip install -e ."
  exit 1
fi

mkdir -p "$ROOT/logs"
mkdir -p "$HOME/Library/LaunchAgents"
"$PYTHON" - "$ROOT" "$DEST" "$PYTHON" "$LABEL" <<'PY'
import sys
from pathlib import Path

root, dest, python, label = sys.argv[1:]
template = Path(root) / "scripts" / "com.applyapp.daily.plist.template"
text = template.read_text().format(
    label=label,
    python=python,
    root=root,
    logfile=f"{root}/logs/daily.log",
)
Path(dest).write_text(text)
print(f"Wrote {dest}")
PY

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl enable "gui/$(id -u)/$LABEL"
echo "Scheduled ApplyApp for 7:00 local time. Test with: launchctl kickstart -k gui/$(id -u)/$LABEL"
