#!/usr/bin/env bash
set -e

echo "====================================================================="
echo " StreamVault - YouTube to MP4 & MP3 Local Media Utility"
echo "====================================================================="
echo ""

# 1. Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 is not installed or not in your PATH."
    echo "Please install Python 3.10+ using your package manager (brew, apt, dnf)."
    exit 1
fi

# 2. Check Node.js
if ! command -v node &>/dev/null; then
    echo "[WARNING] Node.js was not detected in your PATH."
    echo "yt-dlp uses Node.js to solve YouTube player challenges."
    echo "Install via: brew install node (macOS) or sudo apt install nodejs (Ubuntu/Debian)"
    echo ""
fi

# 3. Check FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "[WARNING] FFmpeg was not detected in PATH."
    echo "MP3 conversion and 1080p+ video merging require FFmpeg."
    echo "Install via: brew install ffmpeg (macOS) or sudo apt install ffmpeg (Ubuntu/Debian)"
    echo ""
fi

# 4. Create virtualenv if not present
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment in ./venv ..."
    python3 -m venv venv
fi

# Activate virtualenv
source venv/bin/activate

# 5. Check & install dependencies
echo "[*] Ensuring dependencies are installed..."
pip install --upgrade pip >/dev/null 2>&1 || true
pip install -r backend/requirements.txt

# 6. Launch Application on port 3000
echo ""
echo "[*] Starting StreamVault on http://localhost:3000 ..."
echo "[*] Press Ctrl+C to stop the server."
echo ""

python3 backend/app.py
