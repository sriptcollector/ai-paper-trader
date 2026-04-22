@echo off
echo ============================================
echo Setting up Daily Trading Schedule
echo ============================================
echo.
echo This will create a Windows Task Scheduler job
echo to run the paper trader daily at 4:30 PM ET.
echo.

set PYTHON_PATH=python
set SCRIPT_PATH=%~dp0scheduled_trade.py

schtasks /create /tn "AI Paper Trader - Daily" /tr "%PYTHON_PATH% \"%SCRIPT_PATH%\"" /sc daily /st 16:30 /f

echo.
echo Task created! The paper trader will run daily at 4:30 PM.
echo.
echo To view: schtasks /query /tn "AI Paper Trader - Daily"
echo To delete: schtasks /delete /tn "AI Paper Trader - Daily" /f
echo.
pause
