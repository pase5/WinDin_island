@echo off
setlocal
echo ========================================================
echo   WinDin-Link Windows Firewall Configuration (Port 8765)
echo ========================================================
echo.

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator elevation via UAC...
    echo (Please click YES on the Windows prompt that appears)
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: Running with Administrator rights
echo [OK] Running with Administrator privileges.
echo Configuring inbound rule for TCP port 8765 (Private + Public)...
echo.

:: Delete any previous rule with this name to avoid duplicates
netsh advfirewall firewall delete rule name="WinDin-Link Continuity Bridge" >nul 2>&1

:: Add the firewall rule
netsh advfirewall firewall add rule name="WinDin-Link Continuity Bridge" dir=in action=allow protocol=TCP localport=8765 profile=any

if %errorLevel% equ 0 (
    echo.
    echo ========================================================
    echo   SUCCESS: WinDin-Link firewall rule added successfully!
    echo   Inbound traffic on port 8765 is now allowed.
    echo ========================================================
) else (
    echo.
    echo [ERROR] Failed to add firewall rule. Error code: %errorLevel%
)

echo.
pause
