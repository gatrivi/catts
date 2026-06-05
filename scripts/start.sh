#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d .venv ]]; then
  echo "Run: python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
exec python server.py
