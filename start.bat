@echo off
echo ============================================
echo    NexSearch - Mini Search Engine
echo ============================================
echo.

echo [1/3] Checking Elasticsearch...
curl -s http://localhost:9200 > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Elasticsearch not running!
    echo     Download from: https://www.elastic.co/downloads/elasticsearch
    echo     Run: bin\elasticsearch.bat
    pause
    exit /b 1
)
echo [OK] Elasticsearch is running.
echo.

echo [2/3] Installing Python dependencies...
pip install -r requirements.txt -q
echo [OK] Dependencies installed.
echo.

echo [3/3] Starting FastAPI backend...
echo [OK] API will be at: http://127.0.0.1:8000
echo [OK] Open frontend/index.html in your browser
echo.
echo Press Ctrl+C to stop the server.
echo.
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
