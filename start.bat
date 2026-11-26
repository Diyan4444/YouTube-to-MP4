@echo off
setlocal enabledelayedexpansion
title StreamVault - YouTube to MP4 & MP3 Media Utility

echo =====================================================================
echo  StreamVault - YouTube to MP4 & MP3 Local Media Utility
echo =====================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python 3.10 or higher from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Check Node.js (recommended for yt-dlp challenge solving)
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Node.js was not detected in your PATH.
    echo yt-dlp uses Node.js to solve YouTube JavaScript player challenges.
    echo While basic formats may work, we strongly recommend installing Node.js from:
    echo https://nodejs.org/
    echo.
)

:: 3. Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg was not detected in PATH.
    echo Audio extraction (MP3) and high-resolution video merging (1080p, 1440p, 4K)
    echo require FFmpeg.
    echo Install via winget: winget install Gyan.FFmpeg
    echo or download from: https://ffmpeg.org/download.html
    echo.
)

:: 4. Check & Install Dependencies
echo [*] Checking Python dependencies...
python -c "import flask, flask_cors, yt_dlp" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing required dependencies from backend\requirements.txt...
    pip install -r backend\requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies. Please check your internet connection.
        pause
        exit /b 1
    )
)

:: 5. Launch Application on port 3000
echo.
echo [*] Starting StreamVault on http://localhost:3000 ...
echo [*] Press Ctrl+C in this terminal window to stop the application.
echo.

python backend\app.py

if %errorlevel% neq 0 (
    echo.
    echo [INFO] Application exited with error code %errorlevel%.
    pause
)
