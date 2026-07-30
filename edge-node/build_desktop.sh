#!/bin/bash

# Build Script for REC Edge Node Desktop App
# Converts the Python PyQt app into a standalone executable

echo "Preparing build environment..."
cd "$(dirname "$0")"

echo "Setting up Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing PyInstaller and dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "Building standalone desktop app..."
# Compile with --noconsole (windowed mode) and --onedir to fix cv2 decompression errors
pyinstaller --noconsole --onedir \
    --name "RECDashboard" \
    --add-data "camera:camera" \
    --add-data "orchestrator:orchestrator" \
    desktop_app.py

echo "Build complete."
echo "Executable located at: dist/RECDashboard/RECDashboard"
echo "On macOS, PyInstaller also generates a .app bundle in the dist folder."
deactivate
