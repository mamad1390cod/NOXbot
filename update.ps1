# --------------------------------------------------------------------------- #
#  NOXbot - update the local copy from GitHub (Windows)
#
#  This script is safe to run in three ways:
#
#    1) Bootstrap (the file does not exist locally yet - recommended first time):
#         irm https://raw.githubusercontent.com/mamad1390cod/NOXbot/refs/heads/arena/01a0726c-noxbot/update.ps1 | iex
#
#    2) From the project folder, after the first update:
#         powershell -ExecutionPolicy Bypass -File I:\python\NOXbot\update.ps1
#
#    3) Double-click update.bat (same thing, no PowerShell knowledge needed).
#
#  Your private files are NEVER touched: .env, noxbot.db, logs\, backups\,
#  exports\ are git-ignored, so updating the source leaves them exactly as is.
# --------------------------------------------------------------------------- #

[CmdletBinding()]
param(
    [string]$ProjectDir = "I:\python\NOXbot",
    [string]$RepoUrl    = "https://github.com/mamad1390cod/NOXbot.git",
    [string]$Branch     = "arena/01a0726c-noxbot",
    [switch]$SkipTests,
    [switch]$SkipBackup
)

# Native commands (git/python) write progress to stderr. With
# $ErrorActionPreference='Stop' Windows PowerShell 5.1 turns that into a
# NativeCommandError and aborts mid-way, so exit codes are checked manually.
$ErrorActionPreference = 'Continue'

function Write-Step   ($m) { Write-Host "`n>> $m" -ForegroundColor Cyan }
function Write-Ok     ($m) { Write-Host "   OK  $m" -ForegroundColor Green }
function Write-Warn   ($m) { Write-Host "   !   $m" -ForegroundColor Yellow }
function Write-Fail   ($m) { Write-Host "   X   $m" -ForegroundColor Red }

function Invoke-Git {
    # git's own output is printed with Write-Host on purpose: anything written
    # to the pipeline would be returned together with the exit code and break
    # the "-ne 0" checks below.
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git @GitArgs 2>&1 | ForEach-Object { Write-Host "   $_" }
    return $LASTEXITCODE
}

function Require-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Fail "Git is not installed (or not on PATH)."
        Write-Host "   Install it from https://git-scm.com/download/win, reopen the terminal, run again."
        throw "git-missing"
    }
    Write-Ok ("git found: " + (git --version))
}

function Get-Python {
    # Windows installs expose either "python" or the "py -3" launcher.
    foreach ($candidate in @(
        @{ Exe = 'python'; Pre = @() },
        @{ Exe = 'py';     Pre = @('-3') }
    )) {
        if (Get-Command $candidate.Exe -ErrorAction SilentlyContinue) {
            $probe = $candidate.Pre + @('--version')
            & $candidate.Exe @probe 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

function Invoke-Py {
    param([hashtable]$Python, [string[]]$Arguments)
    $all = $Python.Pre + $Arguments
    & $Python.Exe @all 2>&1 | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

try {
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "  NOXbot updater - $Branch" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor Cyan

    # --- 0) Preconditions ------------------------------------------------------- #
    Write-Step "Checking the project folder"
    if (-not (Test-Path -LiteralPath $ProjectDir)) {
        Write-Fail "Folder not found: $ProjectDir"
        Write-Host "   Run again with the right path, e.g.:"
        Write-Host "   .\update.ps1 -ProjectDir 'D:\my\path\NOXbot'"
        throw 'update-aborted'
    }
    Set-Location -LiteralPath $ProjectDir
    Write-Ok $ProjectDir

    Require-Git

    # --- 1) Backup on the very first run ---------------------------------------- #
    $isRepo = Test-Path -LiteralPath (Join-Path $ProjectDir ".git")

    if (-not $isRepo -and -not $SkipBackup) {
        Write-Step "First run - backing up the current folder"
        $backup = Join-Path (Split-Path $ProjectDir -Parent) ("NOXbot_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
        # robocopy skips the virtualenv/caches so the backup takes seconds, not minutes.
        robocopy $ProjectDir $backup /E /XD ".venv" "venv" "env" "__pycache__" ".git" ".pytest_cache" /XF "*.pyc" /NFL /NDL /NJH /NJS /NC /NS | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Warn "robocopy reported code $LASTEXITCODE - check $backup" }
        else { Write-Ok "backup: $backup" }
        $global:LASTEXITCODE = 0
    }

    # --- 2) Connect the folder to GitHub / refresh the remote ------------------- #
    if (-not $isRepo) {
        Write-Step "Linking this folder to GitHub (first run)"
        if ((Invoke-Git init) -ne 0) { throw 'git init failed' }
        if ((Invoke-Git remote add origin $RepoUrl) -ne 0) { Write-Warn "remote 'origin' already existed" }
    } else {
        Write-Step "Existing git checkout detected"
    }
    Invoke-Git remote set-url origin $RepoUrl | Out-Null

    # --- 3) Fetch + move to the latest commit ----------------------------------- #
    Write-Step "Downloading the latest code"
    if ((Invoke-Git fetch origin $Branch) -ne 0) {
        Write-Fail "Could not reach GitHub. Check your internet/proxy/VPN and try again."
        throw 'update-aborted'
    }

    Write-Step "Applying the update"
    # checkout -f handles every case in one step: first run over existing files,
    # a normal update, and a branch whose history was rewritten upstream.
    # Only *tracked* source files are replaced; .env / noxbot.db / logs stay put.
    if ((Invoke-Git checkout -f -B $Branch FETCH_HEAD) -ne 0) {
        Write-Fail "git checkout failed - send me the message above."
        throw 'update-aborted'
    }
    $head = (git rev-parse --short HEAD)
    Write-Ok "now on $Branch @ $head"

    # --- 4) .env ---------------------------------------------------------------- #
    Write-Step "Checking .env"
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir ".env"))) {
        Copy-Item ".env.example" ".env"
        Write-Warn ".env was missing - created from the template."
        Write-Host "   Open .env and set BOT_TOKEN and OWNER_ID before starting the bot."
    } else {
        Write-Ok ".env found (untouched)"
    }

    # --- 5) Dependencies -------------------------------------------------------- #
    $py = Get-Python
    if (-not $py) {
        Write-Warn "Python not found on PATH - skipping dependency install and tests."
        Write-Host "   Install Python 3.12+ from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')."
    } else {
        $probeArgs = $py.Pre + @('--version')
        $version = (& $py.Exe @probeArgs 2>&1)
        Write-Ok "python: $version"

        Write-Step "Installing dependencies"
        Invoke-Py $py @('-m', 'pip', 'install', '--upgrade', 'pip', '--quiet') | Out-Null
        $code = Invoke-Py $py @('-m', 'pip', 'install', '-r', 'requirements.txt')
        if ($code -ne 0) { throw 'pip install failed - see the message above' }
        Write-Ok "runtime dependencies installed"

        if (-not $SkipTests) {
            Write-Step "Running the health checks"
            Invoke-Py $py @('-m', 'pip', 'install', '-r', 'requirements-dev.txt', '--quiet') | Out-Null
            $testsCode = Invoke-Py $py @('-m', 'pytest', 'tests/', '-q')
            $auditCode = Invoke-Py $py @('tools/audit_buttons.py')
            if ($testsCode -eq 0) { Write-Ok "test suite passed" } else { Write-Warn "tests reported problems (code $testsCode)" }
            if ($auditCode -eq 0) { Write-Ok "button audit clean" } else { Write-Warn "button audit found issues (code $auditCode)" }
        }
    }

    Write-Host "`n==================================================" -ForegroundColor Green
    Write-Host "  Update finished - commit $head" -ForegroundColor Green
    Write-Host "  Start the bot with:  python main.py" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Red
    Write-Host "  Update aborted: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Copy everything above and send it to me." -ForegroundColor Red
    Write-Host "==================================================" -ForegroundColor Red
}
