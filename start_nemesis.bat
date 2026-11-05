@echo off
title N.E.M.E.S.I.S. Supreme Commander Launcher
cd /d "%~dp0\nemesis-core"
echo [1/3] Reconnecting Wireless Android Swarm Bridge...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "Gateway"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        .\platform-tools\adb.exe connect %%b:5555 >nul 2>&1
    )
)
echo [2/3] Launching N.E.M.E.S.I.S. HUD in Chrome...
start "" "http://localhost:8000"
echo [3/3] Starting FastAPI Ring-0 Kernel on Port 8000...
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
pause
