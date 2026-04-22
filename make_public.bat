@echo off
echo ============================================
echo Making Dashboard Publicly Accessible
echo ============================================
echo.
echo Option 1: Use Streamlit Community Cloud (recommended)
echo   - Push this project to GitHub
echo   - Go to share.streamlit.io
echo   - Connect your repo and deploy dashboard.py
echo.
echo Option 2: Use localhost.run (quick tunneling)
echo   Starting tunnel now...
echo.
ssh -R 80:localhost:8501 nokey@localhost.run
