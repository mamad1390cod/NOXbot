@echo off
REM ---------------------------------------------------------------------------
REM  NOXbot - update from the GitHub ZIP (no git needed)
REM
REM  Double-click this file, or run the same thing as a one-liner:
REM
REM    curl -L -o "%TEMP%\nox.zip" "https://github.com/mamad1390cod/NOXbot/raw/refs/heads/arena/01a0726c-noxbot/NOXbot.zip" && powershell -NoProfile -Command "Expand-Archive '%TEMP%\nox.zip' '%TEMP%\noxupd' -Force" && robocopy "%TEMP%\noxupd\NOXbot" "I:\python\NOXbot" /E /NFL /NDL /NJH /NJS /NC /NS & cd /d I:\python\NOXbot && python tools\doctor.py --fix
REM
REM  It MERGES the new files over the project: your .env, noxbot.db, logs\,
REM  backups\ and any extra module of your own are left untouched.
REM ---------------------------------------------------------------------------
setlocal

set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"
if not exist "%PROJ%\main.py" set "PROJ=I:\python\NOXbot"

set "ZIPURL=https://github.com/mamad1390cod/NOXbot/raw/refs/heads/arena/01a0726c-noxbot/NOXbot.zip"
set "ZIPFILE=%TEMP%\NOXbot_update.zip"
set "UNPACK=%TEMP%\NOXbot_update"

echo ==================================================
echo   NOXbot ZIP updater
echo   folder : %PROJ%
echo ==================================================

if not exist "%PROJ%\main.py" (
    echo [X] Project not found at %PROJ%
    goto :fail
)

echo.
echo ^>^> Downloading the latest ZIP...
curl -L --fail -o "%ZIPFILE%" "%ZIPURL%"
if errorlevel 1 (
    echo [X] Download failed - check your internet / VPN.
    goto :fail
)

echo ^>^> Unpacking...
if exist "%UNPACK%" rmdir /s /q "%UNPACK%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIPFILE%' -DestinationPath '%UNPACK%' -Force"
if not exist "%UNPACK%\NOXbot\main.py" (
    echo [X] The archive does not look right.
    goto :fail
)

echo ^>^> Backing up the current folder...
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "DT=%%I"
if defined DT (
    robocopy "%PROJ%" "%PROJ%_backup_%DT:~0,8%_%DT:~8,6%" /E /XD ".venv" "venv" "env" "__pycache__" ".git" ".pytest_cache" /XF "*.pyc" /NFL /NDL /NJH /NJS /NC /NS >nul
    echo     backup: %PROJ%_backup_%DT:~0,8%_%DT:~8,6%
)

echo ^>^> Copying the new files in...
REM /E merges and overwrites; nothing is deleted, so .env, noxbot.db, logs\ and
REM your own extra modules stay. The updater scripts are skipped here because
REM this very file is running - they are refreshed at the end.
robocopy "%UNPACK%\NOXbot" "%PROJ%" /E /XF "update.bat" "update.ps1" "update-zip.bat" /NFL /NDL /NJH /NJS /NC /NS >nul
if errorlevel 8 (
    echo [X] Copy failed.
    goto :fail
)
echo     files updated.

where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not on PATH - skipping dependencies, doctor and tests.
    goto :done
)

echo.
echo ^>^> Installing dependencies...
python -m pip install -r "%PROJ%\requirements.txt" --quiet

echo.
echo ^>^> Repairing modules that cannot be imported (doctor)...
cd /d "%PROJ%"
python tools\doctor.py --fix

echo.
echo ^>^> Running the tests...
python -m pip install -r requirements-dev.txt --quiet
python -m pytest tests/ -q

:done
REM Refresh the updater scripts themselves after this file is done executing.
start "" /b cmd /c "timeout /t 3 >nul & copy /y "%UNPACK%\NOXbot\update*.*" "%PROJ%" >nul"

echo.
echo ==================================================
echo   Update complete. Restart the bot:  python main.py
echo ==================================================
pause
exit /b 0

:fail
echo.
echo Update aborted.
pause
exit /b 1
