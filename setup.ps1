# GitMind Setup for Windows
# Run: Unblock-File .\setup.ps1; .\setup.ps1

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   GitMind Setup (Windows)"              -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$DIR  = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = "$DIR\.venv"

# Check Python
try {
    $pyver = python --version 2>&1
    Write-Host "OK: $pyver found" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Check 'Add Python to PATH' during install." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Create venv
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv "$VENV"
if (-not (Test-Path "$VENV\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Failed to create venv." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Set-Location $DIR
& "$VENV\Scripts\Activate.ps1"

# Install packages
Write-Host "Installing packages (1-2 minutes)..." -ForegroundColor Cyan
python -m pip install -q --upgrade pip
python -m pip install -r "$DIR\requirements.txt"
Write-Host "OK: Packages installed" -ForegroundColor Green

# Create folders
New-Item -ItemType Directory -Force -Path "$DIR\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$DIR\logs" | Out-Null

# Create gitmind.bat
$batContent = "@echo off`r`ncall `"$VENV\Scripts\activate.bat`"`r`ncd /d `"$DIR`"`r`npython main.py %*"
[System.IO.File]::WriteAllText("$DIR\gitmind.bat", $batContent, [System.Text.Encoding]::ASCII)
Write-Host "OK: gitmind.bat created" -ForegroundColor Green

# Add to PATH
Write-Host ""
$addPath = Read-Host "Add gitmind to PATH so you can run it from anywhere? [Y/n]"
if ($addPath -ne "n" -and $addPath -ne "N") {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -notlike "*$DIR*") {
        [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$DIR", "User")
        Write-Host "OK: Added to PATH (restart terminal after this)" -ForegroundColor Green
    } else {
        Write-Host "INFO: Already in PATH" -ForegroundColor Yellow
    }
}

# Daily notification schedule
Write-Host ""
$startup = Read-Host "Schedule a daily GitMind notification? [Y/n]"
if ($startup -ne "n" -and $startup -ne "N") {
    $timeInput = Read-Host "What time should it run? (e.g. 18:00 for 6 PM, 09:00 for 9 AM)"
    try {
        $parsedTime = [datetime]::ParseExact($timeInput.Trim(), "HH:mm", $null)
    } catch {
        Write-Host "Invalid time format, defaulting to 18:00" -ForegroundColor Yellow
        $parsedTime = [datetime]::ParseExact("18:00", "HH:mm", $null)
    }
    $taskName   = "GitMind_Daily"
    $pythonExe  = "$VENV\Scripts\python.exe"
    $scriptPath = "$DIR\main.py"
    $action     = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`" --notify" -WorkingDirectory $DIR
    $trigger    = New-ScheduledTaskTrigger -Daily -At $parsedTime
    $settings   = New-ScheduledTaskSettingsSet -StartWhenAvailable
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null
    Write-Host "OK: Daily notification scheduled at $($parsedTime.ToString('HH:mm'))" -ForegroundColor Green
}

# Add to PowerShell profile (runs when terminal opens)
Write-Host ""
$addProfile = Read-Host "Run GitMind every time you open PowerShell? [Y/n]"
if ($addProfile -ne "n" -and $addProfile -ne "N") {
    $profileDir = Split-Path $PROFILE
    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    }
    if (-not (Test-Path $PROFILE)) {
        New-Item -ItemType File -Force -Path $PROFILE | Out-Null
    }
    $existing = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
    if ($existing -notlike "*gitmind*") {
        $line = "`n# GitMind`n$DIR\gitmind.bat"
        Add-Content -Path $PROFILE -Value $line -Encoding UTF8
        Write-Host "OK: Added to PowerShell profile" -ForegroundColor Green
    } else {
        Write-Host "INFO: Already in profile" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Run GitMind now:" -ForegroundColor White
Write-Host "  .\gitmind.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "You need a FREE Groq API key - GitMind will ask for it." -ForegroundColor Yellow
Write-Host "Get it at: https://console.groq.com" -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to launch GitMind now"

Set-Location $DIR
& "$VENV\Scripts\Activate.ps1"
python main.py
