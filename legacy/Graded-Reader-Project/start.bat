@echo off
where python >nul 2>&1 || (echo Python not found. Install from python.org & pause & exit /b 1)
echo Installing dependencies...
pip install -r requirements.txt -q
echo.
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop
echo.
python -m uvicorn app:app --reload --port 8000 --log-config log_config.json
