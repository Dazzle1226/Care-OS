#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install -r "$ROOT_DIR/backend/requirements.txt"
export PYTHONPATH="$ROOT_DIR/backend"

python3 "$ROOT_DIR/backend/scripts/seed_demo.py"

npm --prefix "$ROOT_DIR/frontend" install

uvicorn app.main:app --app-dir "$ROOT_DIR/backend" --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

npm --prefix "$ROOT_DIR/frontend" run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
