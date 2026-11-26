# ⚡ StreamVault — YouTube to MP4 & MP3 Media Utility

An open-source, fully self-hosted local media utility built with Python Flask, yt-dlp, FFmpeg, and an Obsidian + Burnt Orange UI.

StreamVault runs entirely on your own computer on **`http://localhost:3000`** with zero external cloud or hosting dependencies.

---

## ✨ Features

- 🎬 **MP4 Video Downloads**: Download videos up to 4K (2160p) when available from the source with lossless audio/video FFmpeg stream-merging.
- 🎵 **MP3 Audio Extraction**: Extract audio encoded with high-efficiency MP3 bitrates (128, 192, 256, and 320 kbps) with preserved metadata.
- 🔍 **Real Format Detection**: Genuinely extracts available adaptive resolutions without artificial 360p caps.
- 📊 **Live Progress & Indeterminate States**: Real-time download percentage, transfer speed, and ETA with animated status transitions during FFmpeg processing.
- 🛑 **One-Click Cancellation**: Halt active media processing and automatically reclaim temporary storage.
- 🔄 **Safe Error Recovery**: Clear status alerts with instant retry affordance.
- 🔒 **Zero Cloud Dependencies & Privacy**: All media processing, format parsing, and storage happen locally on your own machine.
- ⚡ **Single-Origin Simplicity**: Flask serves both the modern frontend and the API on port `3000`.

---

## 📸 Screenshots

*(Placeholder: Add screenshots of the Obsidian + Burnt Orange UI here)*

---

## 📋 Prerequisites

Before installing, ensure the following core tools are installed on your machine:

1. **Python 3.10+**: [Download Python](https://www.python.org/downloads/) *(Ensure "Add Python to PATH" is checked on Windows)*.
2. **FFmpeg**: [Download FFmpeg](https://ffmpeg.org/download.html) *(Required for MP3 audio extraction and 1080p+ MP4 stream merging)*.
3. **Node.js**: [Download Node.js](https://nodejs.org/) *(Recommended: used by yt-dlp to solve YouTube player challenges)*.
4. **Git**: [Download Git](https://git-scm.com/downloads).

---

## 📦 Installation

Clone the repository to your local computer:

```bash
git clone https://github.com/Diyan4444/yt-to-mp4.git
cd "yt to mp4"
```

StreamVault features an automated installation system that checks for existing dependencies and installs only what is missing:

---

## 🪟 Windows Setup

1. Double-click or run the automated installer:
   ```cmd
   install.bat
   ```
   *The installer automatically detects Python, installs missing tools via `winget` if needed, sets up a local Python virtual environment, and installs required Python packages from `backend/requirements.txt`.*

2. Start the application:
   ```cmd
   start.bat
   ```

3. Open **`http://localhost:3000`** in your browser.

---

## 🍎 macOS Setup

1. Make the setup scripts executable and run the automated installer:
   ```bash
   chmod +x install.sh start.sh
   ./install.sh
   ```
   *The script detects installed dependencies and uses Homebrew to install missing software (such as FFmpeg or Node.js) when available, then configures a local Python virtual environment.*

2. Start the application:
   ```bash
   ./start.sh
   ```

3. Open **`http://localhost:3000`** in your browser.

---

## 🐧 Linux Setup

1. Make the setup scripts executable and run the automated installer:
   ```bash
   chmod +x install.sh start.sh
   ./install.sh
   ```
   *The installer detects your package manager (`apt`, `dnf`, `pacman`), installs missing system dependencies, creates the Python virtual environment, and installs dependencies.*

2. Start the application:
   ```bash
   ./start.sh
   ```

3. Open **`http://localhost:3000`** in your browser.

---

## 🚀 Running the Application

To run the application at any time:

- **Windows**: `start.bat`
- **macOS / Linux**: `./start.sh`

The application will bind to:

👉 **`http://localhost:3000`**

To stop the server, press `Ctrl+C` in your terminal window.

---

## 📖 How to Use

1. Open **`http://localhost:3000`** in your web browser.
2. **Paste** any legitimate YouTube URL (supports `/watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`).
3. Click **Analyze** (or press Enter) to extract stream metadata and thumbnail.
4. **Select Format**: Switch between **🎬 MP4 Video** and **🎵 MP3 Audio**.
5. **Select Quality**: Choose your desired video resolution (up to 4K) or MP3 bitrate (128–320 kbps).
6. Click **Generate MP4** or **Generate MP3**.
7. Once processing completes, your browser will automatically save the file directly to your local download directory.

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, Modern CSS Variables, Vanilla JavaScript (Zero external JS frameworks).
- **Backend**: Python 3, Flask.
- **Media Engine**: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp-ejs), [FFmpeg](https://ffmpeg.org/).
- **Database & Job State**: Embedded SQLite (WAL mode, persistent concurrency control).
- **Design System**: Obsidian (`#111111`) + Burnt Orange (`#E58A3A`) with Space Grotesk and Inter typography.

---

## 📄 License

This project is licensed under the **Apache License, Version 2.0** — see the [LICENSE](LICENSE) file or visit [https://www.apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0) for details.
