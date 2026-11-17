#!/bin/bash
# Opens the show's timing editor in your browser. Double-click it in Finder.
# The first time, it sets up what the editor needs inside this folder (.venv); that takes a minute or two.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "The editor needs Python 3.10 or newer, and this Mac's python3 is older."
  echo "Install one with:  brew install python@3.12   then double-click this file again."
  read -r -p "Press Return to close." _; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Setting up (first time only)..."
  "$PY" -m venv .venv || { read -r -p "Could not set up. Press Return to close." _; exit 1; }
fi
.venv/bin/python -m pip -q install --upgrade pip >/dev/null 2>&1
.venv/bin/python -m pip -q install -e . || { read -r -p "Could not install what the editor needs. Press Return to close." _; exit 1; }
cd shows/crown || exit 1
echo "The editor is open in your browser. Leave this window open while you use it; close it to stop."
exec ../../.venv/bin/python -m script_to_screen.tools.editor "${1:-the-council}"
