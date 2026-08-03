#!/bin/bash

# Edge Node Startup Script
# This script initializes the local Python environment and boots the capture daemon.

echo "=========================================================="
echo " 📷 INITIALIZING EDGE NODE (Realtime Event Capture) "
echo "=========================================================="

echo "[1/3] Setting up Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  -> Created new venv."
else
    echo "  -> venv already exists."
fi

echo "[2/3] Activating environment and verifying dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt
echo "  -> Dependencies are up to date."

echo "[3/3] Booting Local Photographer Dashboard..."
python web_dashboard.py
