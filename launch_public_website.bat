@echo off
title N.E.M.E.S.I.S. // Live HTTPS Public Website Tunnel
cd /d "%~dp0"
echo ====================================================================
echo   N.E.M.E.S.I.S. LIVE HTTPS PUBLIC WEBSITE GENERATOR
echo   (Creates a secure https://*.trycloudflare.com URL for Friends
echo    and PayPal Hackathon Reviewers with Camera & Mic support!)
echo ====================================================================

if not exist "cloudflared.exe" (
    echo [1/2] Downloading official Cloudflare HTTPS Tunnel binary...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
)

echo [2/2] Opening secure HTTPS tunnel to http://localhost:8000 ...
echo COPY THE "https://xxxx.trycloudflare.com" LINK BELOW AND SHARE IT!
echo.
cloudflared.exe tunnel --url http://localhost:8000
pause
