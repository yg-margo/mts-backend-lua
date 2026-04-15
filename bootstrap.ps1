# One-command launcher for reviewers/organizers on Windows (PowerShell).
#
# Usage:   powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
# Stops:   Ctrl+C, then `docker compose down` to remove containers.

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

function Log([string]$msg)  { Write-Host "[bootstrap] $msg" -ForegroundColor Cyan }
function Fail([string]$msg) { Write-Host "[bootstrap] ERROR: $msg" -ForegroundColor Red; exit 1 }

# 1. Docker installed?
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker не найден. Установите Docker Desktop: https://www.docker.com/products/docker-desktop/"
}

# 2. Docker daemon running?
try {
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
} catch {
    Fail "Docker daemon не запущен. Запустите Docker Desktop и повторите."
}

# 3. Detect NVIDIA GPU
$profile = "cpu"
Log "Проверяем GPU (docker run --gpus all busybox) ..."
docker run --rm --gpus all --entrypoint true busybox:latest *> $null
if ($LASTEXITCODE -eq 0) {
    $profile = "gpu"
    Log "NVIDIA GPU доступен. Профиль: gpu"
} else {
    Log "GPU не обнаружен или драйверы не проброшены. Профиль: cpu (будет медленно, но запустится)"
}

# 4. Build + up
Log "Запуск: docker compose --profile $profile up --build"
Log "Первый старт качает ~5 GB (образ Ollama + qwen2.5-coder:7b)."
Log "Ждите в логах строки '=== WARMUP DONE ===' — после неё открывайте http://localhost:8080"
Write-Host ""
docker compose --profile $profile up --build
exit $LASTEXITCODE
