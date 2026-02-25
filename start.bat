@echo off
title MSIE Backend
echo ============================================
echo   MSIE - Starting all services
echo ============================================
echo.

set MEMURAI_PATH=C:\Program Files\Memurai
set MEMURAI_EXE=%MEMURAI_PATH%\memurai.exe
set MEMURAI_CLI=%MEMURAI_PATH%\memurai-cli.exe
set WEB_DIR=%~dp0..\media-integrity-engine

:: ---- 1. Redis (Memurai) ----
echo [1/4] Starting Redis (Memurai)...
"%MEMURAI_CLI%" ping >nul 2>&1
if %errorlevel% neq 0 (
    start "MSIE Memurai" /min "%MEMURAI_EXE%"
    timeout /t 2 /nobreak >nul
)
echo   [OK] Redis
echo.

:: ---- 2. Migrations ----
echo [2/4] Applying migrations...
python manage.py migrate --no-input
echo.

:: ---- 3. Celery Worker ----
echo [3/4] Starting Celery worker...
start "MSIE Celery" cmd /k "title MSIE Celery && cd /d "%~dp0" && python -m celery -A config worker --loglevel=info --pool=solo"
timeout /t 3 /nobreak >nul
echo   [OK] Celery worker started.
echo.

:: ---- 4. Frontend ----
echo [4/4] Starting Frontend (Next.js)...
start "MSIE Frontend" cmd /k "title MSIE Frontend && cd /d "%WEB_DIR%" && npm run dev"
echo   [OK] Next.js started.
echo.

:: ---- Django Server ----
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   Press Ctrl+C to stop Django
echo ============================================
python manage.py runserver 0.0.0.0:8000
