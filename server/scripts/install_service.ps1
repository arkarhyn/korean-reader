# Install korean-reader as a Windows service (DECISIONS O4: NSSM) with a
# tailscale cert for HTTPS (DECISIONS O1). Run once from an ELEVATED PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File server\scripts\install_service.ps1
#
# Re-running is safe: it re-issues the cert and reconfigures the service.
# Prereqs: `cd server; uv sync`, `cd web; npm run build`, Tailscale logged in.

$ErrorActionPreference = "Stop"

$Service   = "korean-reader"
$Port      = 8443
$Repo      = (Resolve-Path "$PSScriptRoot\..\..").Path
$Server    = Join-Path $Repo "server"
$Python    = Join-Path $Server ".venv\Scripts\python.exe"
$DataRoot  = "C:\ProgramData\korean-reader"
$CertDir   = Join-Path $DataRoot "certs"
$LogDir    = Join-Path $DataRoot "logs"
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this from an elevated (Administrator) PowerShell." }
if (-not (Test-Path $Python)) { throw "Missing $Python -- run 'cd server; uv sync' first." }
if (-not (Test-Path (Join-Path $Repo "web\dist\index.html"))) { throw "web/dist missing -- run 'cd web; npm run build' first." }

# 1. NSSM
$Nssm = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $Nssm) {
    choco install nssm -y
    $Nssm = "C:\ProgramData\chocolatey\bin\nssm.exe"
}

# 2. Cert (outside the repo, DECISIONS 22)
New-Item -ItemType Directory -Force $CertDir, $LogDir | Out-Null
& "$PSScriptRoot\renew_cert.ps1" -NoRestart
$HostName = (& $Tailscale status --json | ConvertFrom-Json).Self.DNSName.TrimEnd(".")

# 3. Service
if (Get-Service $Service -ErrorAction SilentlyContinue) {
    & $Nssm stop $Service | Out-Null
} else {
    & $Nssm install $Service $Python | Out-Null
}
& $Nssm set $Service Application $Python | Out-Null
& $Nssm set $Service AppParameters "scripts\serve.py" | Out-Null
& $Nssm set $Service AppDirectory $Server | Out-Null
& $Nssm set $Service AppEnvironmentExtra `
    "SERVER_HOST=0.0.0.0" "SERVER_PORT=$Port" `
    "TLS_CERT_PATH=$CertDir\server.crt" "TLS_KEY_PATH=$CertDir\server.key" `
    "PYTHONUTF8=1" | Out-Null
& $Nssm set $Service DisplayName "Korean Reader" | Out-Null
& $Nssm set $Service Start SERVICE_AUTO_START | Out-Null
& $Nssm set $Service AppStdout "$LogDir\service.log" | Out-Null
& $Nssm set $Service AppStderr "$LogDir\service.log" | Out-Null
& $Nssm set $Service AppRotateFiles 1 | Out-Null
& $Nssm set $Service AppRotateBytes 5000000 | Out-Null
& $Nssm set $Service AppExit Default Restart | Out-Null
& $Nssm set $Service AppRestartDelay 5000 | Out-Null

# 4. Firewall: tailnet addresses only
Get-NetFirewallRule -DisplayName "Korean Reader (tailnet)" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName "Korean Reader (tailnet)" -Direction Inbound -Protocol TCP `
    -LocalPort $Port -RemoteAddress 100.64.0.0/10 -Action Allow | Out-Null

# 5. Cert renewal every 4 weeks (tailscale certs last ~90 days)
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\renew_cert.ps1`""
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 4 -DaysOfWeek Sunday -At 4am
Register-ScheduledTask -TaskName "Korean Reader cert renewal" -Action $action -Trigger $trigger `
    -User "SYSTEM" -RunLevel Highest -Force | Out-Null

& $Nssm start $Service | Out-Null
Start-Sleep -Seconds 4
Get-Service $Service | Format-Table Name, Status -AutoSize
Write-Host "Open https://${HostName}:$Port/ on the iPhone (Tailscale on). Logs: $LogDir\service.log"
