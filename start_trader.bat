@echo off
echo ============================================
echo AI Paper Trader - Full Trading Cycle
echo ============================================
echo.
echo [1/2] Running strategy optimization...
python run_trader.py optimize
echo.
echo [2/2] Running trading cycle...
python run_trader.py trade
echo.
echo Done! Check the dashboard at http://localhost:8501
pause
