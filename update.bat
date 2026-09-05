@echo off
REM ---------------------------------------------------------------------------
REM  NOXbot - one-click update from GitHub (double-click this file)
REM
REM  Uses plain git + python only, so it works on every Windows box without
REM  touching PowerShell execution policies.
REM
REM  Your private files are untouched: .env, noxbot.db, logs\, backups\.
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"
if not exist "%PROJ%\main.py" set "PROJ=I:\python\NOXbot"

set "REPO=https://github.com/mamad1390cod/NOXbot.git"
set "BRANCH=arena/01a0726c-noxbot"

echo ==================================================
echo   NOXbot updater
echo   folder : %PROJ%
echo   branch : %BRANCH%
echo ==================================================

cd /d "%PROJ%" 2>nul
if errorlevel 1 (
    echo [X] Folder not found: %PROJ%
    goto :fail
)

where git >nul 2>nul
if errorlevel 1 (
    echo [X] Git is not installed. Get it from https://git-scm.com/download/win
    goto :fail
)

if not exist "%PROJ%\.git" (
    echo.
    echo ^>^> First run: backing up the current folder...
    for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "DT=%%I"
    set "STAMP=!DT:~0,8!_!DT:~8,6!"
    robocopy "%PROJ%" "%PROJ%_backup_!STAMP!" /E /XD ".venv" "venv" "env" "__pycache__" ".git" ".pytest_cache" /XF "*.pyc" /NFL /NDL /NJH /NJS /NC /NS >nul
    echo     backup: %PROJ%_backup_!STAMP!

    echo ^>^> Linking this folder to GitHub...
    git init
    git remote add origin "%REPO%"
)

git remote set-url origin "%REPO%"

echo.
echo ^>^> Downloading the latest code...
git fetch origin %BRANCH%
if errorlevel 1 (
    echo [X] Could not reach GitHub. Check internet / proxy / VPN.
    goto :fail
)

echo ^>^> Applying the update...
git checkout -f -B %BRANCH% FETCH_HEAD
if errorlevel 1 (
    echo [X] git checkout failed - send me the message above.
    goto :fail
)

for /f %%H in ('git rev-parse --short HEAD') do set "HEAD=%%H"
echo     now on %BRANCH% @ !HEAD!

if not exist "%PROJ%\.env" (
    copy ".env.example" ".env" >nul
    echo [!] .env was missing - created from the template.
    echo     Open .env and set BOT_TOKEN and OWNER_ID before starting the bot.
)

where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found on PATH - skipping dependencies and tests.
    goto :done
)

echo.
echo ^>^> Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [X] pip install failed.
    goto :fail
)

echo.
echo ^>^> Running the health checks...
python -m pip install -r requirements-dev.txt --quiet
python -m pytest tests/ -q
python tools/audit_buttons.py
python tools/doctor.py
if errorlevel 1 (
    echo [!] Some handler modules are disabled. Fix them with:
    echo     python tools/doctor.py --fix
)

:done
echo.
echo ==================================================
echo   Update finished. Start the bot with:  python main.py
echo ==================================================
pause
exit /b 0

:fail
echo.
echo Update aborted.
pause
exit /b 1
