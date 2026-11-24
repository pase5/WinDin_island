# WinDin-Link Windows Firewall Port 8765 Provisioning Script
# Allows inbound TCP connections on port 8765 across both Private Wi-Fi and Public Hotspot profiles.

# 1. Elevate to Administrator if not already running with elevated privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting Administrator privileges to configure Windows Firewall..." -ForegroundColor Yellow
    try {
        Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$PSCommandPath`""
        exit
    } catch {
        Write-Host "Elevation request cancelled or failed. Please run PowerShell as Administrator." -ForegroundColor Red
        exit 1
    }
}

$ruleName = "WinDin-Link Continuity Bridge"

try {
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

    if ($existingRule) {
        Write-Host "Updating existing firewall rule '$ruleName'..." -ForegroundColor Cyan
        Set-NetFirewallRule -DisplayName $ruleName `
          -Direction Inbound `
          -Protocol TCP `
          -LocalPort 8765 `
          -Action Allow `
          -Profile Private,Public
    } else {
        Write-Host "Creating new firewall rule '$ruleName'..." -ForegroundColor Cyan
        New-NetFirewallRule -DisplayName $ruleName `
          -Direction Inbound `
          -Protocol TCP `
          -LocalPort 8765 `
          -Action Allow `
          -Profile Private,Public
    }

    Write-Host "SUCCESS: WinDin-Link firewall rule configured for port 8765 across Private and Public profiles." -ForegroundColor Green
    Write-Host "You can close this window now." -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Failed to configure firewall rule: $_" -ForegroundColor Red
    exit 1
}
