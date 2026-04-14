@echo off
setlocal

set "BACKEND=%~dp0"
set "FRONT=%BACKEND%front"

echo [start.bat] Backend:  %BACKEND%
echo [start.bat] Frontend: %FRONT%
echo.

where python >nul 2>&1 || (echo ERROR: python not on PATH & pause & exit /b 1)
where npm    >nul 2>&1 || (echo ERROR: npm not on PATH    & pause & exit /b 1)
where ollama >nul 2>&1 || echo WARN: ollama not on PATH - backend will fail to generate until it is running on :11434

if not exist "%BACKEND%.venv" (
    echo [start.bat] Creating venv...
    pushd "%BACKEND%" || exit /b 1
    python -m venv .venv || (popd & pause & exit /b 1)
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt || (popd & pause & exit /b 1)
    popd
)

if not exist "%BACKEND%.env" (
    if exist "%BACKEND%.env.example" (
        echo [start.bat] Copying .env.example -^> .env
        copy /Y "%BACKEND%.env.example" "%BACKEND%.env" >nul
    )
)

if not exist "%FRONT%\node_modules" (
    echo [start.bat] Installing frontend deps...
    pushd "%FRONT%" || exit /b 1
    call npm install || (popd & pause & exit /b 1)
    popd
)

echo [start.bat] Launching backend on :8080 and frontend (vite)...
start "mts-backend" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate.bat && python run.py"
start "mts-frontend" cmd /k "cd /d "%FRONT%" && npm run dev"

echo.
echo [start.bat] Backend:  http://localhost:8080/docs
echo [start.bat] Frontend: see the vite window for the URL (usually http://localhost:5173)
echo.
endlocal
