#!/usr/bin/env bash
set -e

echo "====================================================================="
echo " StreamVault - Centralized Dependency Installer (macOS & Linux)"
echo "====================================================================="
echo ""

# 1. DETECT OPERATING SYSTEM
OS_TYPE="$(uname -s)"

# 2. CHECK PYTHON 3
echo "[CHECK] Python 3 runtime..."
if ! command -v python3 &>/dev/null; then
    echo "[MISSING] Python 3 is not installed."
    if [ "$OS_TYPE" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            echo "[*] Installing Python 3 via Homebrew..."
            brew install python
        else
            echo "[ERROR] Homebrew not found. Please install Python from https://www.python.org/downloads/"
            exit 1
        fi
    elif [ -f /etc/debian_version ]; then
        echo "[*] Installing Python 3 via apt..."
        sudo apt update && sudo apt install -y python3 python3-pip python3-venv
    elif [ -f /etc/fedora-release ] || [ -f /etc/redhat-release ]; then
        echo "[*] Installing Python 3 via dnf..."
        sudo dnf install -y python3 python3-pip
    elif [ -f /etc/arch-release ]; then
        echo "[*] Installing Python 3 via pacman..."
        sudo pacman -Sy --noconfirm python python-pip
    else
        echo "[ERROR] Unsupported OS. Please install Python 3.10+ manually."
        exit 1
    fi
else
    echo "[FOUND] $(python3 --version)"
fi

# 3. CHECK NODE.JS
echo ""
echo "[CHECK] Node.js runtime..."
if ! command -v node &>/dev/null; then
    echo "[MISSING] Node.js is not installed."
    if [ "$OS_TYPE" = "Darwin" ] && command -v brew &>/dev/null; then
        echo "[*] Installing Node.js via Homebrew..."
        brew install node
    elif [ -f /etc/debian_version ]; then
        echo "[*] Installing Node.js via apt..."
        sudo apt update && sudo apt install -y nodejs
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y nodejs
    else
        echo "[WARNING] Could not auto-install Node.js. Recommended for yt-dlp: https://nodejs.org/"
    fi
else
    echo "[FOUND] Node.js $(node --version)"
fi

# 4. CHECK FFMPEG
echo ""
echo "[CHECK] FFmpeg media tools..."
if ! command -v ffmpeg &>/dev/null; then
    echo "[MISSING] FFmpeg was not detected in PATH."
    if [ "$OS_TYPE" = "Darwin" ] && command -v brew &>/dev/null; then
        echo "[*] Installing FFmpeg via Homebrew..."
        brew install ffmpeg
    elif [ -f /etc/debian_version ]; then
        echo "[*] Installing FFmpeg via apt..."
        sudo apt update && sudo apt install -y ffmpeg
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y ffmpeg
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm ffmpeg
    else
        echo "[WARNING] Could not auto-install FFmpeg. Please install manually from https://ffmpeg.org/download.html"
    fi
else
    echo "[FOUND] FFmpeg is available and configured."
fi

# 5. SETUP PYTHON VIRTUAL ENVIRONMENT & DEPENDENCIES
echo ""
echo "[CHECK] Python virtual environment..."
if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment in ./venv ..."
    python3 -m venv venv
    echo "[CREATED] Virtual environment created."
else
    echo "[FOUND] Existing virtual environment detected."
fi

echo ""
echo "[*] Activating virtual environment and installing packages..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r backend/requirements.txt

echo "[SUCCESS] Python dependencies verified."
echo ""
echo "====================================================================="
echo " Installation complete! You can now start StreamVault by running:"
echo " ./start.sh"
echo "====================================================================="
echo ""
