@echo off
title N.E.M.E.S.I.S. v3.0 // Public HTTPS Tunnel
cd /d "%~dp0"
if not exist "cloudflared.exe" (
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
)
echo ====================================================================
echo   OPENING STABLE HTTP/2 IPv4 PUBLIC TUNNEL TO PORT 8000
echo ====================================================================
cloudflared.exe tunnel --protocol http2 --edge-ip-version 4 --url http://localhost:8000
pause
