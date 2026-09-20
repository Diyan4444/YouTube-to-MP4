import os
import re
import uuid
import tempfile
import threading
import shutil
import time
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp

# ============================================================
# APP INITIALIZATION
# ============================================================

# Point static/template folder to the frontend folder
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# ============================================================
# CONFIGURATION
# ============================================================

DOWNLOAD_ROOT = os.path.join(tempfile.gettempdir(), "yt_mp4_downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# Max concurrent downloads to protect server memory/CPU
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", 5))
download_semaphore = threading.BoundedSemaphore(MAX_CONCURRENT_DOWNLOADS)

# ============================================================
# FFMPEG RESOLUTION
# ============================================================

def resolve_ffmpeg():
    """Dynamically resolve ffmpeg directory/executable for Windows, Linux, and Cloud environments."""
    # 1. Check environment variable override
    env_ffmpeg = os.environ.get("FFMPEG_PATH") or os.environ.get("FFMPEG_LOCATION")
    if env_ffmpeg:
        if os.path.isdir(env_ffmpeg):
            return env_ffmpeg
        if os.path.isfile(env_ffmpeg):
            return os.path.dirname(env_ffmpeg)

    # 2. Check system PATH via shutil.which
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return os.path.dirname(system_ffmpeg)

    # 3. Known fallback Windows winget/local paths
    win_winget = (
        r"C:\Users\Diyan\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-9.0-full_build\bin"
    )
    if os.path.isdir(win_winget):
        return win_winget

    return None

FFMPEG_DIR = resolve_ffmpeg()
FFMPEG_AVAILABLE = bool(
    FFMPEG_DIR and os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
) or bool(shutil.which("ffmpeg"))

if FFMPEG_DIR:
    print(f"[INFO] FFmpeg detected at: {FFMPEG_DIR}")
else:
    print("[WARN] FFmpeg was not detected in PATH or standard locations.")

# ============================================================
# STATE & LOCKS
# ============================================================

downloads = {}
downloads_lock = threading.Lock()

ALLOWED_QUALITIES = [144, 240, 360, 480, 720, 1080, 1440, 2160]

# ============================================================
# URL VALIDATION & SECURITY
# ============================================================

YOUTUBE_REGEX = re.compile(
    r"^(https?://)?(www\.|m\.)?(youtube\.com/(watch\?v=|shorts/|embed/)|youtu\.be/)[a-zA-Z0-9_-]{6,12}"
)

def validate_youtube_url(url: str) -> bool:
    if not url or len(url) > 1024:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = (parsed.hostname or "").lower()
        if not (
            hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
            or hostname == "youtu.be"
        ):
            return False
        return bool(YOUTUBE_REGEX.match(url))
    except Exception:
        return False

def clean_error(error) -> str:
    if not error:
        return "Unknown error."
    error = str(error)
    # Remove ANSI terminal escapes
    error = re.sub(r"\x1b\[[0-9;]*m", "", error)
    # Strip sensitive local paths if any
    error = re.sub(r"[a-zA-Z]:\\[^ \t\n\r\f\v]+", "[path]", error)
    return error.strip()

def get_quality_label(height: int) -> str:
    labels = {
        2160: "2160p (4K)",
        1440: "1440p (2K)",
        1080: "1080p (Full HD)",
        720: "720p (HD)",
        480: "480p",
        360: "360p",
        240: "240p",
        144: "144p",
    }
    return labels.get(height, f"{height}p")

# ============================================================
# FRONTEND & HEALTH ROUTES
# ============================================================

@app.route("/", methods=["GET"])
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return send_file(index_file)
    return jsonify({
        "status": "online",
        "service": "YouTube Downloader API",
        "ffmpeg": FFMPEG_AVAILABLE
    })

@app.route("/<path:filename>", methods=["GET"])
def serve_static(filename):
    if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/health", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "ffmpeg": FFMPEG_AVAILABLE,
        "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
        "active_jobs": len(downloads)
    })

# ============================================================
# GET FORMATS & VIDEO INFO
# ============================================================

@app.route("/formats", methods=["POST"])
@app.route("/api/formats", methods=["POST"])
def get_formats():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON request."}), 400

    video_url = str(data.get("url", "")).strip()
    if not video_url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    if not validate_youtube_url(video_url):
        return jsonify({"error": "Invalid or unsupported YouTube URL format."}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 3,
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb", "ios", "android", "web"]
                }
            }
        }
        if os.environ.get("YOUTUBE_COOKIES"):
            cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write(os.environ["YOUTUBE_COOKIES"])
            ydl_opts["cookiefile"] = cookie_path
        elif os.path.isfile("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"

        if FFMPEG_DIR:
            ydl_opts["ffmpeg_location"] = FFMPEG_DIR

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        formats = info.get("formats", [])
        available_video = {}
        has_audio = False

        for fmt in formats:
            # Check for audio presence
            if fmt.get("acodec") != "none" or fmt.get("ext") in ("m4a", "webm", "opus", "mp3"):
                has_audio = True

            height = fmt.get("height")
            if not height:
                continue

            try:
                height = int(height)
            except (ValueError, TypeError):
                continue

            if fmt.get("vcodec") == "none":
                continue

            if height not in ALLOWED_QUALITIES:
                continue

            # Check video format
            current = available_video.get(height)
            current_tbr = current.get("tbr", 0) if current else 0
            new_tbr = fmt.get("tbr", 0) or 0

            # Prefer MP4 format container or higher bitrate
            if current is None or (fmt.get("ext") == "mp4" and current.get("ext") != "mp4") or (new_tbr > current_tbr):
                available_video[height] = fmt

        # Construct available video options sorted ascending
        video_qualities = []
        for quality in ALLOWED_QUALITIES:
            if quality in available_video:
                video_qualities.append({
                    "height": quality,
                    "label": get_quality_label(quality),
                    "ext": "mp4"
                })

        # Provide audio MP3 options if audio is present
        audio_options = []
        if has_audio:
            audio_options = [
                {"quality": "128", "label": "MP3 Audio (128 kbps)", "ext": "mp3"},
                {"quality": "192", "label": "MP3 Audio (192 kbps - High)", "ext": "mp3"},
                {"quality": "320", "label": "MP3 Audio (320 kbps - Best)", "ext": "mp3"}
            ]

        # Extract thumbnail
        thumbnails = info.get("thumbnails", [])
        thumbnail_url = thumbnails[-1].get("url") if thumbnails else info.get("thumbnail", "")

        # Format duration
        duration_secs = info.get("duration", 0)
        minutes, seconds = divmod(duration_secs or 0, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            duration_str = f"{minutes}:{seconds:02d}"

        return jsonify({
            "success": True,
            "title": info.get("title", "YouTube Video"),
            "uploader": info.get("uploader", ""),
            "duration": duration_str,
            "thumbnail": thumbnail_url,
            "qualities": video_qualities,
            "audio_options": audio_options
        })

    except Exception as e:
        app.logger.exception("Format extraction failed")
        return jsonify({"error": clean_error(str(e))}), 500

# ============================================================
# START DOWNLOAD ROUTE
# ============================================================

@app.route("/start-download", methods=["POST"])
@app.route("/api/start-download", methods=["POST"])
def start_download():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON request."}), 400

    video_url = str(data.get("url", "")).strip()
    media_type = str(data.get("type", "mp4")).lower().strip()
    quality = data.get("quality")

    if not video_url:
        return jsonify({"error": "Please enter a YouTube URL."}), 400

    if not validate_youtube_url(video_url):
        return jsonify({"error": "Invalid or unsupported YouTube URL."}), 400

    if media_type not in ("mp4", "mp3"):
        return jsonify({"error": "Unsupported media type. Must be 'mp4' or 'mp3'."}), 400

    if media_type == "mp4":
        if quality is None:
            return jsonify({"error": "Please select a video quality."}), 400
        try:
            quality = int(quality)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid quality format."}), 400
        if quality not in ALLOWED_QUALITIES:
            return jsonify({"error": "Unsupported video quality."}), 400
    elif media_type == "mp3":
        quality = str(quality or "192")
        if quality not in ("128", "192", "320"):
            quality = "192"

    download_id = str(uuid.uuid4())
    download_folder = os.path.join(DOWNLOAD_ROOT, download_id)
    os.makedirs(download_folder, exist_ok=True)

    with downloads_lock:
        downloads[download_id] = {
            "status": "starting",
            "percent": 0,
            "speed": "",
            "eta": "",
            "filename": None,
            "media_type": media_type,
            "error": None,
            "folder": download_folder,
            "created": time.time()
        }

    thread = threading.Thread(
        target=download_worker,
        args=(download_id, video_url, media_type, quality, download_folder),
        daemon=True
    )
    thread.start()

    return jsonify({
        "success": True,
        "download_id": download_id
    })

# ============================================================
# DOWNLOAD WORKER THREAD
# ============================================================

def download_worker(download_id, video_url, media_type, quality, download_folder):
    # Acquire semaphore to respect concurrent download limits
    acquired = download_semaphore.acquire(blocking=True, timeout=120)
    if not acquired:
        with downloads_lock:
            if download_id in downloads:
                downloads[download_id]["status"] = "error"
                downloads[download_id]["error"] = "Server is currently at capacity. Please try again shortly."
        return

    try:
        def progress_hook(data):
            try:
                status = data.get("status")
                if status == "downloading":
                    downloaded = data.get("downloaded_bytes") or 0
                    total = data.get("total_bytes") or data.get("total_bytes_estimate")
                    percent = (downloaded / total * 100) if total else 0

                    with downloads_lock:
                        if download_id in downloads:
                            downloads[download_id]["status"] = "downloading"
                            downloads[download_id]["percent"] = round(percent, 1)
                            downloads[download_id]["speed"] = data.get("_speed_str") or ""
                            downloads[download_id]["eta"] = data.get("_eta_str") or ""

                elif status == "finished":
                    with downloads_lock:
                        if download_id in downloads:
                            downloads[download_id]["percent"] = 100
                            downloads[download_id]["status"] = "converting"
                            downloads[download_id]["speed"] = ""
                            downloads[download_id]["eta"] = ""
            except Exception as hook_err:
                app.logger.warning(f"Progress hook warning: {hook_err}")

        # yt-dlp configuration based on media type
        outtmpl_pattern = os.path.join(download_folder, "%(title)s.%(ext)s")

        if media_type == "mp3":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl_pattern,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "socket_timeout": 30,
                "progress_hooks": [progress_hook],
                "extractor_args": {
                    "youtube": {
                        "player_client": ["mweb", "ios", "android", "web"]
                    }
                },
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(quality),
                }],
            }
        else: # mp4
            format_selector = (
                f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={quality}]+bestaudio/"
                f"best[height<={quality}][ext=mp4]/"
                f"best[height<={quality}]"
            )
            ydl_opts = {
                "format": format_selector,
                "merge_output_format": "mp4",
                "outtmpl": outtmpl_pattern,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "fragment_retries": 5,
                "socket_timeout": 30,
                "progress_hooks": [progress_hook],
                "extractor_args": {
                    "youtube": {
                        "player_client": ["mweb", "ios", "android", "web"]
                    }
                },
                "continuedl": True,
                "overwrites": True
            }

        if os.environ.get("YOUTUBE_COOKIES"):
            cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
            ydl_opts["cookiefile"] = cookie_path
        elif os.path.isfile("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"

        if FFMPEG_DIR:
            ydl_opts["ffmpeg_location"] = FFMPEG_DIR

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

        # Locate final generated file
        final_file = None
        target_ext = f".{media_type}"
        base_name = os.path.splitext(filename)[0]

        direct_candidate = base_name + target_ext
        if os.path.isfile(direct_candidate):
            final_file = direct_candidate
        elif os.path.isfile(filename):
            final_file = filename
        else:
            # Fallback search directory
            for f in os.listdir(download_folder):
                full_p = os.path.join(download_folder, f)
                if os.path.isfile(full_p) and f.lower().endswith(target_ext):
                    final_file = full_p
                    break

        if not final_file or not os.path.isfile(final_file):
            raise FileNotFoundError(f"Completed extraction, but final {media_type.upper()} file could not be located.")

        with downloads_lock:
            if download_id in downloads:
                downloads[download_id]["status"] = "completed"
                downloads[download_id]["percent"] = 100
                downloads[download_id]["filename"] = final_file
                downloads[download_id]["speed"] = ""
                downloads[download_id]["eta"] = ""

        print(f"[SUCCESS] Download completed ({media_type}): {final_file}")

    except Exception as e:
        app.logger.exception("Download failed")
        error_msg = clean_error(str(e))
        with downloads_lock:
            if download_id in downloads:
                downloads[download_id]["status"] = "error"
                downloads[download_id]["error"] = error_msg

        # Clean folder on failure
        try:
            if os.path.exists(download_folder):
                shutil.rmtree(download_folder, ignore_errors=True)
        except Exception:
            pass

    finally:
        download_semaphore.release()

# ============================================================
# PROGRESS POLLING
# ============================================================

@app.route("/progress/<download_id>", methods=["GET"])
@app.route("/api/progress/<download_id>", methods=["GET"])
def progress(download_id):
    with downloads_lock:
        download = downloads.get(download_id)

    if not download:
        return jsonify({"error": "Download ID not found."}), 404

    return jsonify({
        "status": download["status"],
        "percent": download["percent"],
        "speed": download["speed"],
        "eta": download["eta"],
        "error": download["error"]
    })

# ============================================================
# DOWNLOAD FINAL FILE
# ============================================================

@app.route("/download-file/<download_id>", methods=["GET"])
@app.route("/api/download-file/<download_id>", methods=["GET"])
def download_file(download_id):
    with downloads_lock:
        download = downloads.get(download_id)

    if not download:
        return jsonify({"error": "Download ID not found."}), 404

    if download["status"] != "completed":
        return jsonify({"error": "Download has not completed yet."}), 400

    file_path = download.get("filename")
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Media file is missing or has expired."}), 404

    media_type = download.get("media_type", "mp4")
    mimetype = "audio/mpeg" if media_type == "mp3" else "video/mp4"

    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name=os.path.basename(file_path),
            mimetype=mimetype
        )
    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 500

# ============================================================
# BACKGROUND CLEANUP TASK
# ============================================================

def cleanup_old_downloads():
    while True:
        try:
            now = time.time()
            with downloads_lock:
                items = list(downloads.items())

            for d_id, data in items:
                # Expire downloads older than 30 minutes
                if now - data.get("created", now) > 1800:
                    folder = data.get("folder")
                    if folder and os.path.exists(folder):
                        shutil.rmtree(folder, ignore_errors=True)
                    with downloads_lock:
                        downloads.pop(d_id, None)
        except Exception as e:
            app.logger.error(f"Cleanup error: {e}")

        time.sleep(300)

cleanup_thread = threading.Thread(target=cleanup_old_downloads, daemon=True)
cleanup_thread.start()

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print(f"YouTube Downloader Server starting on port {port}")
    print(f"FFmpeg available: {FFMPEG_AVAILABLE}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)