#!/usr/bin/env bash
set -euo pipefail

BACKEND="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONT="$BACKEND/front"

echo "[start.sh] Backend:  $BACKEND"
echo "[start.sh] Frontend: $FRONT"
echo

command -v python3 >/dev/null || { echo "ERROR: python3 not on PATH"; exit 1; }
command -v npm     >/dev/null || { echo "ERROR: npm not on PATH"; exit 1; }
command -v ollama  >/dev/null || echo "WARN: ollama not on PATH - backend will fail to generate until it is running on :11434"

if [ ! -d "$BACKEND/.venv" ]; then
  echo "[start.sh] Creating venv..."
  python3 -m venv "$BACKEND/.venv"
  # shellcheck disable=SC1091
  source "$BACKEND/.venv/bin/activate"
  pip install -r "$BACKEND/requirements.txt"
  deactivate
fi

if [ ! -f "$BACKEND/.env" ] && [ -f "$BACKEND/.env.example" ]; then
  echo "[start.sh] Copying .env.example -> .env"
  cp "$BACKEND/.env.example" "$BACKEND/.env"
fi

if [ ! -d "$FRONT/node_modules" ]; then
  echo "[start.sh] Installing frontend deps..."
  (cd "$FRONT" && npm install)
fi

echo "[start.sh] Launching backend on :8080 and frontend (vite)..."
echo "[start.sh] Backend:  http://localhost:8080/docs"
echo "[start.sh] Frontend: see vite output below (usually http://localhost:5173)"
echo "[start.sh] Ctrl+C to stop both."
echo

BACKEND_PID=""
FRONT_PID=""
cleanup() {
  echo
  echo "[start.sh] Stopping..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONT_PID" ]   && kill "$FRONT_PID"   2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$BACKEND"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec python run.py
) &
BACKEND_PID=$!

(
  cd "$FRONT"
  exec npm run dev
) &
FRONT_PID=$!

wait
