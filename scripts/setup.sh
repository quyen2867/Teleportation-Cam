#!/usr/bin/env bash
# macOS setup: virtual environment, dependencies and the verified AI models.
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3.12}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Không tìm thấy $PYTHON. Cài bằng: brew install python@3.12" >&2
  exit 1
fi

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m animecam.models --download

echo "Xong. Chạy ứng dụng: ./scripts/run.sh"
