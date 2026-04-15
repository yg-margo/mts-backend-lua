#!/usr/bin/env bash
# One-command launcher for reviewers/organizers.
# Works on macOS, Linux, WSL2, and Git Bash on Windows.
#
# Usage:    ./bootstrap.sh
# Stops:    Ctrl+C, then `docker compose down` to remove containers.

set -e

cd "$(dirname "$0")"

log() { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[bootstrap] ERROR:\033[0m %s\n' "$*" >&2; }

# 1. Docker installed?
if ! command -v docker >/dev/null 2>&1; then
    err "Docker не найден. Установите Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# 2. Docker daemon running?
if ! docker info >/dev/null 2>&1; then
    err "Docker daemon не запущен. Запустите Docker Desktop и повторите."
    exit 1
fi

# 3. Detect NVIDIA GPU via docker (works on Linux-native + WSL2).
PROFILE="cpu"
log "Проверяем GPU (docker run --gpus all busybox) ..."
if docker run --rm --gpus all --entrypoint true busybox:latest >/dev/null 2>&1; then
    PROFILE="gpu"
    log "NVIDIA GPU доступен. Профиль: gpu"
else
    log "GPU не обнаружен или драйверы не проброшены. Профиль: cpu (будет медленно, но запустится)"
fi

# 4. Build + up
log "Запуск: docker compose --profile ${PROFILE} up --build"
log "Первый старт качает ~5 GB (образ Ollama + qwen2.5-coder:7b + nomic-embed-text)."
log "Ждите в логах строки '=== WARMUP DONE ===' — после неё открывайте http://localhost:8080"
echo
exec docker compose --profile "${PROFILE}" up --build
