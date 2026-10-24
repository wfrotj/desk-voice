@echo off
cd /d "%~dp0"
if not exist voice-receiver.pid exit /b 0
for /f %%p in (voice-receiver.pid) do taskkill /PID %%p /F >nul 2>&1
del /f /q voice-receiver.pid >nul 2>&1
