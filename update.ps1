# --------------------------------------------------------------------------- #
#  NOXbot — update the local copy from GitHub (Windows PowerShell)
#
#  Usage (from anywhere):
#      powershell -ExecutionPolicy Bypass -File I:\python\NOXbot\update.ps1
#
#  What it does:
#    * keeps your .env, noxbot.db, logs/, backups/, exports/ untouched
#    * turns the folder into a git clone the first time it runs
#    * pulls the latest code afterwards
#    * reinstalls dependencies and runs the test-suite so you know it is healthy
# --------------------------------------------------------------------------- #

$ErrorActionPreference = "Stop"

$ProjectDir = "I:\python\NOXbot"
$RepoUrl    = "https://github.com/mamad1390cod/NOXbot.git"
$Branch     = "arena/01a0726c-noxbot"

Write-Host "== NOXbot update ==" -ForegroundColor Cyan
Set-Location $ProjectDir

if (-not (Test-Path (Join-Path $ProjectDir ".git"))) {
    Write-Host "First run: linking this folder to GitHub..." -ForegroundColor Yellow

    $backup = Join-Path (Split-Path $ProjectDir -Parent) ("NOXbot_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    Write-Host "Backing up the current folder to $backup"
    Copy-Item -Path $ProjectDir -Destination $backup -Recurse -Force

    git init | Out-Null
    git remote add origin $RepoUrl
    git fetch origin $Branch
    # -f: replace tracked source files with the GitHub version.
    # .env / noxbot.db / logs / backups are git-ignored, so they are NOT touched.
    git checkout -f -B $Branch FETCH_HEAD
} else {
    git fetch origin $Branch
    git checkout -B $Branch --track origin/$Branch 2>$null | Out-Null
    git pull --ff-only origin $Branch
}

Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if (-not (Test-Path (Join-Path $ProjectDir ".env"))) {
    Copy-Item ".env.example" ".env"
    Write-Host "`n.env created from the template — open it and put your BOT_TOKEN/OWNER_ID in." -ForegroundColor Yellow
}

Write-Host "`nRunning the health checks..." -ForegroundColor Cyan
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -q
python tools/audit_buttons.py

Write-Host "`nDone. Start the bot with:  python main.py" -ForegroundColor Green
