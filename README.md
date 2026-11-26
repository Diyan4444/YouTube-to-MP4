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

Before installing, ensure the following software is installed on your machine:

1. **Python 3.10+**: [Download Python](https://www.python.org/downloads/) *(Check "Add Python to PATH" on Windows)*.
2. **FFmpeg**: [Download FFmpeg](https://ffmpeg.org/download.html) *(Required for MP3 audio extraction and 1080p+ MP4 stream merging)*.
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Ubuntu/Debian: `sudo apt install ffmpeg`
3. **Node.js**: [Download Node.js](https://nodejs.org/) *(Recommended: used by yt-dlp to solve YouTube player challenges)*.
4. **Git**: [Download Git](https://git-scm.com/downloads).

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Diyan4444/yt-to-mp4.git
cd "yt to mp4"
```

---

### Windows Setup

#### Option A: One-Click Startup Script (Recommended)
Simply double-click or run:
```cmd
start.bat
```
The script will verify your Python, Node.js, and FFmpeg installations, install missing Python packages, and start the application.

#### Option B: Manual Setup
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
python backend/app.py
```

---

### macOS & Linux Setup

#### Option A: One-Click Startup Script
```bash
chmod +x start.sh
./start.sh
```

#### Option B: Manual Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
python3 backend/app.py
```

---

## 🌐 Accessing the Application

Once started, open your web browser and navigate to:

👉 **[http://localhost:3000](http://localhost:3000)**

*(Press `Ctrl+C` in your terminal to stop the server).*

---

## 📖 How to Use

1. **Open** `http://localhost:3000` in your web browser.
2. **Paste** any legitimate YouTube URL (supports `/watch?v=`, `youtu.be/`, `/shorts/`, `/embed/`).
3. Click **Analyze** (or press Enter) to extract stream metadata and thumbnail.
4. **Select Format**: Switch between **🎬 MP4 Video** and **🎵 MP3 Audio**.
5. **Select Quality**: Choose your desired video resolution (up to 4K) or MP3 bitrate (128–320 kbps).
6. Click **Generate MP4** or **Generate MP3**.
7. Once processing completes, your browser will automatically download the file to your computer.

---

## 📁 Project Structure

```text
yt-to-mp4/
├── backend/
│   ├── app.py              # Main Flask application, SQLite job manager, streaming
│   └── requirements.txt    # Python dependencies (Flask, Flask-Cors, yt-dlp, yt-dlp-ejs)
├── frontend/
│   └── index.html          # Single-page UI (Obsidian + Burnt Orange, Vanilla JS)
├── tests/
│   └── test_app.py         # Automated unit & integration tests
├── Dockerfile              # Optional self-hosted container build
├── start.bat               # Windows one-click startup script
├── start.sh                # macOS/Linux startup script
├── .gitignore              # Git ignore rules
├── LICENSE                 # MIT License
└── README.md               # Documentation
```

---

## 🐳 Docker (Optional Local Deployment)

You can also run StreamVault locally via Docker:

```bash
docker build -t streamvault .
docker run -p 3000:3000 streamvault
```

Then visit `http://localhost:3000`.

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| **Port 3000 is already in use** | Another process is listening on port 3000. | Stop the conflicting application or terminate it via PowerShell: `Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess \| Stop-Process` |
| **FFmpeg not detected** | FFmpeg is not in your system PATH. | Install via `winget install Gyan.FFmpeg` (Windows) or `brew install ffmpeg` (macOS), then restart your terminal. |
| **Node.js not detected** | Node.js is missing. | Install Node.js from [nodejs.org](https://nodejs.org/) to enable `yt-dlp-ejs` player challenge solving. |
| **Video extraction failed** | Network timeout or outdated yt-dlp. | Run `pip install --upgrade yt-dlp yt-dlp-ejs` to get the latest YouTube extractors. |
| **Download stuck / cancelled** | User cancelled or connection dropped. | Click **Retry** on the error alert to re-queue the job. |

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, Modern CSS Variables, Vanilla JavaScript (Zero external JS frameworks).
- **Backend**: Python 3, Flask, Gunicorn.
- **Media Engine**: [yt-dlp](https://github.com/yt-dlp/yt-dlp), [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp-ejs), [FFmpeg](https://ffmpeg.org/).
- **Database & Job State**: Embedded SQLite (WAL mode, multi-worker safe).
- **Design System**: Obsidian (`#111111`) + Burnt Orange (`#E58A3A`) with Space Grotesk and Inter fonts.

---

## 🤝 Contributing

Contributions are welcome!
1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Run tests to ensure no regressions: `python -m unittest discover tests`.
4. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
5. Push to the branch (`git push origin feature/AmazingFeature`).
6. Open a Pull Request.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

StreamVault is intended for **personal and educational use only**. Users must possess the rights or permissions required to download and store media and comply with YouTube's Terms of Service and applicable copyright laws.
