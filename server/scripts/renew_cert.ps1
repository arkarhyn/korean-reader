# (Re)issue the tailscale HTTPS cert for this machine and restart the service.
# Run elevated; install_service.ps1 schedules it every 4 weeks as SYSTEM.
param([switch]$NoRestart)

$ErrorActionPreference = "Stop"
$Tailscale = "C:\Program Files\Tailscale\tailscale.exe"
$CertDir   = "C:\ProgramData\korean-reader\certs"

New-Item -ItemType Directory -Force $CertDir | Out-Null
$HostName = (& $Tailscale status --json | ConvertFrom-Json).Self.DNSName.TrimEnd(".")
if (-not $HostName) { throw "Tailscale is not logged in." }

& $Tailscale cert --cert-file "$CertDir\server.crt" --key-file "$CertDir\server.key" $HostName
if ($LASTEXITCODE -ne 0) { throw "tailscale cert failed ($LASTEXITCODE)" }

# The private key is readable by SYSTEM and Administrators only.
icacls "$CertDir\server.key" /inheritance:r /grant:r "SYSTEM:F" "Administrators:F" | Out-Null

if (-not $NoRestart -and (Get-Service korean-reader -ErrorAction SilentlyContinue)) {
    Restart-Service korean-reader
}
