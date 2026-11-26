#!/usr/bin/env bash
set -e

echo "====================================================================="
echo " StreamVault - YouTube to MP4 & MP3 Local Media Utility"
echo "====================================================================="
echo ""

# 1. Check if virtual environment exists
if [ ! -f "venv/bin/python" ]; then
    echo "[WARNING] Virtual environment not found in ./venv."
    echo "Please run './install.sh' first to install required dependencies."
    echo ""
    read -p "Would you like to run ./install.sh now? (y/n): " choice
    if [[ "$choice" =~ ^[Yy]$ ]]; then
        chmod +x install.sh
        ./install.sh
    else
        exit 1
    fi
fi

# 2. Activate virtual environment
source venv/bin/activate

# 3. Launch Application on port 3000
echo "[*] Starting StreamVault on http://localhost:3000 ..."
echo "[*] Press Ctrl+C to stop the server."
echo ""

python3 backend/app.py
