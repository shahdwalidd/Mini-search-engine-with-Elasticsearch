#!/bin/bash
echo "============================================"
echo "   NexSearch - Mini Search Engine"
echo "============================================"
echo

echo "[1/3] Checking Elasticsearch..."
if ! curl -s http://localhost:9200 > /dev/null 2>&1; then
    echo "[!] Elasticsearch not running!"
    echo "    macOS:  brew install elastic/tap/elasticsearch-full && brew services start elasticsearch-full"
    echo "    Linux:  sudo systemctl start elasticsearch"
    echo "    Docker: docker run -d -p 9200:9200 -e 'discovery.type=single-node' -e 'xpack.security.enabled=false' elasticsearch:8.13.0"
    exit 1
fi
echo "[OK] Elasticsearch is running."
echo

echo "[2/3] Installing Python dependencies..."
pip install -r backend/requirements.txt -q
echo "[OK] Dependencies installed."
echo

echo "[3/3] Starting FastAPI backend at http://127.0.0.1:8000"
echo "[OK] Open frontend/index.html in your browser after server starts."
echo
echo "Press Ctrl+C to stop."
echo
cd backend && uvicorn main:app --reload --host 127.0.0.1 --port 8000
