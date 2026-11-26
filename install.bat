@echo off
setlocal enabledelayedexpansion
title StreamVault - Centralized Dependency Installer

echo =====================================================================
echo  StreamVault - Automated Dependency Installation
echo =====================================================================
echo.

:: 1. CHECK PYTHON
echo [CHECK] Python runtime...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [MISSING] Python is not installed or not in PATH.
    echo [*] Attempting to install Python via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [ERROR] Automatic installation of Python failed.
        echo Please manually install Python 3.10+ from: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo [INSTALLED] Python installed. You may need to restart your terminal.
) else (
    for /f "tokens=*" %%i in ('python --version') do echo [FOUND] %%i
)

:: 2. CHECK NODE.JS
echo.
echo [CHECK] Node.js runtime...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [MISSING] Node.js is not installed.
    echo [*] Installing Node.js via winget...
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [WARNING] Automatic installation of Node.js failed.
        echo Node.js is recommended for yt-dlp challenge solving.
        echo You can manually install it later from: https://nodejs.org/
    ) else (
        echo [INSTALLED] Node.js installed successfully.
    )
) else (
    for /f "tokens=*" %%i in ('node --version') do echo [FOUND] Node.js %%i
)

:: 3. CHECK FFMPEG
echo.
echo [CHECK] FFmpeg media tools...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [MISSING] FFmpeg was not detected in PATH.
    echo [*] Installing FFmpeg via winget...
    winget install Gyan.FFmpeg --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [WARNING] Automatic installation of FFmpeg via winget failed.
        echo Audio extraction (MP3) and 1080p+ video merging require FFmpeg.
        echo Please download and add FFmpeg to your PATH from: https://ffmpeg.org/download.html
    ) else (
        echo [INSTALLED] FFmpeg installed successfully via winget.
    )
) else (
    echo [FOUND] FFmpeg is available and configured.
)

:: 4. SETUP VIRTUAL ENVIRONMENT & PYTHON DEPENDENCIES
echo.
echo [CHECK] Python virtual environment...
if not exist "venv" (
    echo [*] Creating virtual environment in .\venv ...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [CREATED] Virtual environment created.
) else (
    echo [FOUND] Existing virtual environment detected.
)

echo.
echo [*] Checking and installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
python -m pip install -r backend\requirements.txt

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies from backend\requirements.txt.
    pause
    exit /b 1
)

echo [SUCCESS] Python dependencies verified and ready.
echo.
echo =====================================================================
echo  Installation complete! You can now start the application by running:
echo  start.bat
echo =====================================================================
echo.
pause
