#!/bin/bash

# Edge Node Startup Script
# Automatically boots the local backend server and opens the dashboard in the default browser.

echo "====================================="
echo "   REC Edge Node Initialization"
echo "====================================="

# Determine root directory
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Attempt to activate Python Virtual Environment
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    echo "Activating virtual environment ($ROOT_DIR/venv)..."
    source "$ROOT_DIR/venv/bin/activate"
elif [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
    echo "Activating virtual environment ($ROOT_DIR/.venv)..."
    source "$ROOT_DIR/.venv/bin/activate"
elif [ -f "$ROOT_DIR/edge-node/venv/bin/activate" ]; then
    echo "Activating virtual environment ($ROOT_DIR/edge-node/venv)..."
    source "$ROOT_DIR/edge-node/venv/bin/activate"
else
    echo "Warning: Virtual environment not found. Falling back to system python."
fi

# Navigate to the edge node directory
cd "$ROOT_DIR/edge-node"

# Make sure dependencies are available
echo "Checking dependencies..."
python -c "import fastapi" 2>/dev/null || {
    echo "Error: Required dependencies not found. Please run: pip install -r requirements.txt"
    exit 1
}

# Kill any existing process on port 5000 to prevent Address Already in Use errors
echo "Cleaning up old processes..."
lsof -ti :5000 | xargs kill -9 2>/dev/null || true

# Start the uvicorn server in the background
echo "Starting Edge Node Server on port 5000..."
python -m dashboard.server &
SERVER_PID=$!

# Comprehensive cleanup trap to kill all child processes, orchestrators, and servers on Ctrl+C
cleanup() {
    echo -e "\n[REC] Stopping Edge Node Server and Orchestrator processes..."
    kill $SERVER_PID 2>/dev/null || true
    pkill -P $$ 2>/dev/null || true
    pkill -f "orchestrator.main" 2>/dev/null || true
    pkill -f "dashboard.server" 2>/dev/null || true
    lsof -ti :5000 | xargs kill -9 2>/dev/null || true
    echo "[REC] All processes stopped cleanly."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Wait for server to boot up
sleep 3

# Determine OS and open browser
echo "Opening Edge Dashboard..."
if which xdg-open > /dev/null
then
  xdg-open http://localhost:5000/login
elif which open > /dev/null
then
  open http://localhost:5000/login
else
  echo "Could not detect web browser. Please navigate manually to http://localhost:5000/login"
fi

echo "Edge Node is running. Press Ctrl+C to terminate."
wait $SERVER_PID
