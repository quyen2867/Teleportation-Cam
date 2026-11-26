#!/usr/bin/env bash
# Run AnimeCam FX from this checkout.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "Chưa có môi trường. Chạy trước: ./scripts/setup.sh" >&2
  exit 1
fi

exec .venv/bin/python main.py "$@"
