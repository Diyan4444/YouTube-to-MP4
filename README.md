# 🎬 YouTube Converter

A lightweight **YouTube → MP4 / MP3 converter** built with Flask, yt-dlp, FFmpeg, and vanilla JavaScript.

## ✨ Features

* 🎥 Download YouTube videos as **MP4**
* 🎵 Extract audio as **MP3**
* ⚙️ Select video quality and audio bitrate
* 🔍 Fetch video title, thumbnail, duration & available formats
* 📊 Real-time download progress, speed & ETA
* 🔒 YouTube URL validation
* 🚦 Concurrent download limiting
* 🧹 Automatic temporary-file cleanup
* 📱 Responsive dark-mode UI
* 🐳 Docker-ready deployment
* ☁️ Render deployment configuration included

## 🛠️ Tech Stack

**Frontend:** HTML, CSS, JavaScript
**Backend:** Python, Flask
**Media:** yt-dlp, FFmpeg
**Deployment:** Docker, Gunicorn, Render

## 📁 Structure

```text
├── backend/
│   ├── app.py
│   └── requirements.txt
├── frontend/
│   └── index.html
├── Dockerfile
├── render.yaml
├── .dockerignore
└── .gitignore
```

## 🚀 Run Locally

```bash
git clone <YOUR_REPOSITORY_URL>
cd "yt to mp4"

python -m venv venv
```

### Windows

```powershell
venv\Scripts\activate
pip install -r backend/requirements.txt
python backend/app.py
```

Open:

```text
http://localhost:5000
```

> **FFmpeg is required** for video/audio conversion.

## 🐳 Docker

```bash
docker build -t yt-to-mp4 .
docker run -p 5000:5000 yt-to-mp4
```

Then open:

```text
http://localhost:5000
```

## 🔌 API

| Endpoint                  | Method | Purpose                           |
| ------------------------- | ------ | --------------------------------- |
| `/api/health`             | GET    | Service health                    |
| `/api/formats`            | POST   | Fetch video information & formats |
| `/api/start-download`     | POST   | Start MP4/MP3 download            |
| `/api/progress/<id>`      | GET    | Check download progress           |
| `/api/download-file/<id>` | GET    | Download completed file           |

## ⚙️ Environment Variables

```text
PORT=5000
MAX_CONCURRENT_DOWNLOADS=5
FFMPEG_PATH=<optional>
FFMPEG_LOCATION=<optional>
YOUTUBE_COOKIES=<optional>
```

## ⚠️ Disclaimer

This project is intended for **personal and educational use**. Users are responsible for complying with YouTube's Terms of Service, copyright laws, and applicable local regulations. Only download content you are legally permitted to download.

## 📄 License

Add your preferred license here, such as **MIT License**.
