@echo off
title N.E.M.E.S.I.S. v3.0 // Localhost & Public Server
cd /d "%~dp0\nemesis-core"
echo ====================================================================
echo   STARTING N.E.M.E.S.I.S. v3.0 SUPREME COMMAND CENTER
echo ====================================================================
start "" http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
