#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Sets up the DYMO LabelWriter 550 for use with better-breeze-checkin on Windows.
    Installs usbipd-win, attaches the printer to WSL2, and creates a login task
    so the printer reconnects after every reboot.

.NOTES
    Run this from an elevated (Admin) PowerShell terminal:
      Set-ExecutionPolicy -Scope Process Bypass
      .\setup\windows-setup.ps1
#>

$ErrorActionPreference = "Stop"
$PrinterName = "DYMO_LabelWriter_550"
$TaskName = "Attach DYMO to WSL2"

# --- Helpers ---

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   $msg" -ForegroundColor Yellow }

# --- 1. Check WSL2 ---

Write-Step "Checking WSL2..."
$wslStatus = wsl --status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL2 is not installed or not configured." -ForegroundColor Red
    Write-Host "Install it with:  wsl --install" -ForegroundColor Yellow
    Write-Host "Then reboot and re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "WSL2 is available."

# --- 2. Install usbipd-win ---

Write-Step "Checking usbipd-win..."
$usbipd = Get-Command usbipd -ErrorAction SilentlyContinue
if (-not $usbipd) {
    Write-Warn "usbipd-win not found. Installing via winget..."
    winget install --id dorssel.usbipd-win --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install usbipd-win. Install manually:" -ForegroundColor Red
        Write-Host "  winget install usbipd" -ForegroundColor Yellow
        exit 1
    }
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    Write-Ok "usbipd-win installed."
} else {
    Write-Ok "usbipd-win already installed."
}

# --- 3. Find DYMO printer ---

Write-Step "Looking for DYMO LabelWriter..."
$devices = usbipd list 2>&1
Write-Host $devices

# DYMO vendor ID is 0922
$dymoLine = ($devices | Select-String "0922") | Select-Object -First 1
if (-not $dymoLine) {
    $dymoLine = ($devices | Select-String -Pattern "DYMO|LabelWriter" -CaseSensitive:$false) | Select-Object -First 1
}

if (-not $dymoLine) {
    Write-Host "No DYMO printer found. Make sure it's plugged in via USB." -ForegroundColor Red
    Write-Host "If it's plugged in, check 'usbipd list' output above." -ForegroundColor Yellow
    exit 1
}

# Extract bus ID (first column, format like "1-3")
$busId = ($dymoLine -split "\s+")[0]
if ($busId -match "^\d+-\d+$") {
    Write-Ok "Found DYMO at bus ID: $busId"
} else {
    # Try harder — sometimes the output format varies
    $busId = [regex]::Match($dymoLine.ToString(), "\d+-\d+").Value
    if (-not $busId) {
        Write-Host "Could not parse bus ID from: $dymoLine" -ForegroundColor Red
        Write-Host "Run 'usbipd list', find the DYMO row, and run manually:" -ForegroundColor Yellow
        Write-Host "  usbipd bind --busid <BUS_ID>" -ForegroundColor Yellow
        Write-Host "  usbipd attach --wsl --busid <BUS_ID>" -ForegroundColor Yellow
        exit 1
    }
    Write-Ok "Found DYMO at bus ID: $busId"
}

# --- 4. Bind and attach ---

Write-Step "Binding and attaching DYMO to WSL2..."
usbipd bind --busid $busId --force 2>&1 | Out-Null
usbipd attach --wsl --busid $busId
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to attach. Try unplugging/replugging the printer and re-run." -ForegroundColor Red
    exit 1
}
Write-Ok "DYMO attached to WSL2."

# --- 5. Install CUPS in WSL2 ---

Write-Step "Setting up CUPS inside WSL2..."
$wslScript = @"
set -e
echo '>> Installing CUPS...'
sudo apt-get update -qq
sudo apt-get install -y -qq cups cups-client > /dev/null 2>&1
sudo usermod -aG lpadmin `$USER 2>/dev/null || true

echo '>> Starting CUPS...'
sudo service cups start 2>/dev/null || sudo systemctl start cups 2>/dev/null || true

echo '>> Detecting printer...'
sleep 2
PRINTER_URI=`$(lpinfo -v 2>/dev/null | grep -i 'usb.*dymo\|usb.*label' | head -1 | awk '{print `$2}')

if [ -z "`$PRINTER_URI" ]; then
    echo 'WARNING: Printer not detected via USB in WSL2.'
    echo 'It may take a moment to appear. Re-run or add manually with:'
    echo "  sudo lpadmin -p $PrinterName -E -v usb://DYMO/LabelWriter%20550 -m everywhere"
    exit 0
fi

echo "   Found: `$PRINTER_URI"
sudo lpadmin -p $PrinterName -E -v "`$PRINTER_URI" -m everywhere 2>/dev/null || \
sudo lpadmin -p $PrinterName -E -v "`$PRINTER_URI" -m raw
sudo cupsenable $PrinterName 2>/dev/null || true
sudo cupsaccept $PrinterName 2>/dev/null || true
sudo lpoptions -d $PrinterName

echo '>> CUPS setup complete. Printer ready.'
lpstat -p $PrinterName 2>/dev/null || true
"@

wsl -u root -- bash -c $wslScript.Replace("`r`n", "`n")
Write-Ok "WSL2 CUPS setup done."

# --- 6. Create scheduled task for reboot persistence ---

Write-Step "Creating login task to re-attach printer after reboot..."

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -Command `"usbipd attach --wsl --busid $busId 2>`$null; wsl -u root -- bash -c 'service cups start 2>/dev/null'`""

$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Re-attaches the DYMO LabelWriter to WSL2 and starts CUPS after login." | Out-Null

Write-Ok "Scheduled task '$TaskName' created."
Write-Ok "The printer will auto-reconnect at every login."

# --- Done ---

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " Setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host " Next steps:"
Write-Host "   1. Open a WSL2 terminal"
Write-Host "   2. cd to the project directory"
Write-Host "   3. docker compose up --build -d"
Write-Host "   4. Open http://localhost:5173 in your browser"
Write-Host ""
Write-Host " To verify printing:"
Write-Host "   wsl -e lpstat -p $PrinterName"
Write-Host ""
