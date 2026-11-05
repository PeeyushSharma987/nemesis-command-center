@echo off
title N.E.M.E.S.I.S. // Supreme Command Center
cd /d "%~dp0\nemesis-core"
echo ===================================================
echo   LAUNCHING N.E.M.E.S.I.S. v2.0 COMMAND CENTER
echo ===================================================
start "" http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
