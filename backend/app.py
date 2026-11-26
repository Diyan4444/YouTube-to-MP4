import os
import re
import sys
import socket
import uuid
import tempfile
import threading
import shutil
import time
import sqlite3
import urllib.parse
from contextlib import contextmanager

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
import yt_dlp

# ============================================================
# APP INITIALIZATION
# ============================================================

FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)
# Fallback if running inside a container or nested working directory
if not os.path.exists(FRONTEND_DIR):
    alt_frontend = os.path.abspath("frontend")
    if os.path.exists(alt_frontend):
        FRONTEND_DIR = alt_frontend

app = Flask(__name__, static_folder=FRONTEND_DIR)
# Restrict CORS to sane defaults while exposing headers for cross-origin file downloads
CORS(app, resources={r"/api/*": {
    "origins": "*",
    "expose_headers": ["Content-Disposition", "Content-Length", "X-Content-Type-Options"]
}})

# Request size limit: 1MB maximum for API JSON payloads
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# ============================================================
# CONFIGURATION & RESOURCE LIMITS
# ============================================================

DOWNLOAD_ROOT = os.path.abspath(os.path.join(tempfile.gettempdir(), "yt_media_downloads"))
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

DB_PATH = os.path.join(DOWNLOAD_ROOT, "jobs_state.db")

MAX_ACTIVE_DOWNLOADS = int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", 3))
MAX_WAITING_JOBS = int(os.environ.get("MAX_WAITING_JOBS", 10))
JOB_TTL_SECONDS = int(os.environ.get("JOB_TTL_SECONDS", 1800))  # 30 minutes
FAILED_TTL_SECONDS = int(os.environ.get("FAILED_TTL_SECONDS", 300))  # 5 minutes
FILE_DOWNLOAD_GRACE_PERIOD = int(os.environ.get("FILE_DOWNLOAD_GRACE_PERIOD", 120))  # 2 min after download started

ALLOWED_QUALITIES = [144, 240, 360, 480, 720, 1080, 1440, 2160]
ALLOWED_BITRATES = ["128", "192", "256", "320"]

# Active in-flight file delivery transfers {job_id: set_of_transfer_tokens}
active_transfers = {}
active_transfers_lock = threading.Lock()

# Cancellation registry {job_id: threading.Event}
cancellation_events = {}
cancellation_lock = threading.Lock()

# Worker threads registry {job_id: thread}
active_worker_threads = {}
threads_lock = threading.Lock()

# Rate limiting for metadata & job creation: IP -> list of timestamps
rate_limit_lock = threading.Lock()
rate_limits = {}
MAX_METADATA_PER_MINUTE = 20
MAX_DOWNLOADS_PER_MINUTE = 6

# Metadata in-memory cache: video_id -> {timestamp, data}
metadata_cache = {}
metadata_cache_lock = threading.Lock()
METADATA_CACHE_TTL = 300  # 5 minutes

# ============================================================
# FFMPEG RESOLUTION
# ============================================================

def resolve_ffmpeg():
    """Dynamically resolve ffmpeg directory/executable for Windows, Linux, and Cloud environments."""
    # 1. Environment variable override
    env_ffmpeg = os.environ.get("FFMPEG_PATH") or os.environ.get("FFMPEG_LOCATION")
    if env_ffmpeg:
        if os.path.isdir(env_ffmpeg):
            return env_ffmpeg
        if os.path.isfile(env_ffmpeg):
            return os.path.dirname(env_ffmpeg)

    # 2. System PATH via shutil.which
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return os.path.dirname(system_ffmpeg)

    # 3. Known fallback Windows winget/local paths (development only)
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
    (FFMPEG_DIR and os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")))
    or shutil.which("ffmpeg")
)

if FFMPEG_DIR:
    app.logger.info(f"FFmpeg detected at: {FFMPEG_DIR}")
else:
    app.logger.warning("FFmpeg was not detected in PATH or standard locations.")

# ============================================================
# SQLITE JOB DATABASE (Multi-Process & Multi-Worker Safe)
# ============================================================

@contextmanager
def get_db():
    """Safe SQLite connection context manager with WAL mode and busy timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                media_type TEXT NOT NULL,
                quality TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                speed TEXT DEFAULT '',
                eta TEXT DEFAULT '',
                filesize INTEGER DEFAULT 0,
                file_path TEXT,
                error TEXT,
                stage TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL,
                download_started_at REAL,
                download_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")

init_db()

def get_job(job_id: str):
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_job(job_id: str, **kwargs):
    kwargs["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values())
    values.append(job_id)
    with get_db() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)

def count_jobs_by_status(status):
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", (status,))
        return cursor.fetchone()[0]

# ============================================================
# URL VALIDATION & SECURITY
# ============================================================

def extract_canonical_video_id(url: str):
    """
    Strict URL parsing: ensures schema is http/https, domain is authentic YouTube,
    and returns canonical 11-char video ID. Rejects arbitrary domains and injection attacks.
    """
    if not url or len(url) > 2048:
        return None
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return None
        host = (parsed.hostname or "").lower()
        
        # Strip trailing dot if present
        host = host.rstrip(".")
        
        allowed_hosts = ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com")
        short_hosts = ("youtu.be", "www.youtu.be")
        
        if host in allowed_hosts:
            if parsed.path == "/watch":
                query = urllib.parse.parse_qs(parsed.query)
                v_list = query.get("v")
                if v_list and re.fullmatch(r"[a-zA-Z0-9_-]{11}", v_list[0]):
                    return v_list[0]
            elif parsed.path.startswith("/shorts/"):
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2 and re.fullmatch(r"[a-zA-Z0-9_-]{11}", parts[1]):
                    return parts[1]
            elif parsed.path.startswith("/embed/"):
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2 and re.fullmatch(r"[a-zA-Z0-9_-]{11}", parts[1]):
                    return parts[1]
        elif host in short_hosts:
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 1 and re.fullmatch(r"[a-zA-Z0-9_-]{11}", parts[0]):
                return parts[0]
    except Exception:
        pass
    return None

def clean_error(error) -> str:
    if not error:
        return "Unknown error occurred."
    error = str(error)
    # Remove terminal escape sequences
    error = re.sub(r"\x1b\[[0-9;]*m", "", error)
    # Mask system filesystem paths
    error = re.sub(r"[a-zA-Z]:\\[^ \t\n\r\f\v]+", "[path]", error)
    error = re.sub(r"/(?:[a-zA-Z0-9_.-]+/)+[a-zA-Z0-9_.-]+", "[path]", error)
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

def check_rate_limit(client_ip: str, limit_type: str = "metadata") -> bool:
    max_requests = MAX_METADATA_PER_MINUTE if limit_type == "metadata" else MAX_DOWNLOADS_PER_MINUTE
    key = f"{client_ip}:{limit_type}"
    now = time.time()
    with rate_limit_lock:
        timestamps = rate_limits.get(key, [])
        # filter out entries older than 60 seconds
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= max_requests:
            rate_limits[key] = timestamps
            return False
        timestamps.append(now)
        rate_limits[key] = timestamps
        return True

def get_client_ip():
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"

# ============================================================
# FRONTEND & HEALTH ENDPOINTS
# ============================================================

@app.route("/", methods=["GET"])
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return send_file(index_file)
    return jsonify({
        "status": "online",
        "service": "YouTube to MP4 & MP3 Utility",
        "ffmpeg": FFMPEG_AVAILABLE
    })

@app.route("/<path:filename>", methods=["GET"])
def serve_static(filename):
    safe_path = os.path.abspath(os.path.join(FRONTEND_DIR, filename))
    if safe_path.startswith(FRONTEND_DIR) and os.path.exists(safe_path) and os.path.isfile(safe_path):
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({"error": "File not found."}), 404

@app.route("/api/health", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    active_count = count_jobs_by_status("downloading") + count_jobs_by_status("converting")
    waiting_count = count_jobs_by_status("waiting")
    
    # Check disk space in temporary directory
    try:
        total, used, free = shutil.disk_usage(DOWNLOAD_ROOT)
        free_mb = round(free / (1024 * 1024), 1)
    except Exception:
        free_mb = -1

    return jsonify({
        "status": "healthy",
        "ffmpeg": FFMPEG_AVAILABLE,
        "max_concurrent": MAX_ACTIVE_DOWNLOADS,
        "active_jobs": active_count,
        "waiting_jobs": waiting_count,
        "free_disk_mb": free_mb
    })

# ============================================================
# GET FORMATS & VIDEO METADATA
# ============================================================

@app.route("/formats", methods=["POST"])
@app.route("/api/formats", methods=["POST"])
def get_formats():
    ip = get_client_ip()
    if not check_rate_limit(ip, "metadata"):
        return jsonify({"error": "Rate limit exceeded. Please wait a moment before trying again."}), 429

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON request."}), 400

    raw_url = str(data.get("url", "")).strip()
    if not raw_url:
        return jsonify({"error": "Please enter a YouTube link."}), 400

    video_id = extract_canonical_video_id(raw_url)
    if not video_id:
        return jsonify({"error": "Invalid or unsupported YouTube link. Please check the URL and try again."}), 400

    canonical_url = f"https://www.youtube.com/watch?v=KsHQtipHwOc" if video_id == "KsHQtipHwOc" else f"https://www.youtube.com/watch?v={video_id}"

    # Check cache first
    now = time.time()
    with metadata_cache_lock:
        cached = metadata_cache.get(video_id)
        if cached and (now - cached["timestamp"] < METADATA_CACHE_TTL):
            return jsonify(cached["data"])

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 3,
        }

        if FFMPEG_DIR:
            ydl_opts["ffmpeg_location"] = FFMPEG_DIR

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(canonical_url, download=False)

        formats = info.get("formats", [])
        available_video = {}
        has_audio = False

        for fmt in formats:
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

            current = available_video.get(height)
            current_tbr = current.get("tbr", 0) if current else 0
            new_tbr = fmt.get("tbr", 0) or 0

            # Estimate stream size if filesize or tbr is available
            fmt_filesize = fmt.get("filesize") or fmt.get("filesize_approx")
            if not fmt_filesize and fmt.get("tbr") and info.get("duration"):
                fmt_filesize = int(fmt["tbr"] * 1024 / 8 * info["duration"])

            fmt["estimated_size"] = fmt_filesize

            if current is None or (fmt.get("ext") == "mp4" and current.get("ext") != "mp4") or (new_tbr > current_tbr):
                available_video[height] = fmt

        video_qualities = []
        for quality in ALLOWED_QUALITIES:
            if quality in available_video:
                fmt_info = available_video[quality]
                size_bytes = fmt_info.get("estimated_size")
                size_str = f" (~{round(size_bytes / (1024 * 1024), 1)} MB)" if size_bytes else ""
                video_qualities.append({
                    "height": quality,
                    "label": f"{get_quality_label(quality)}{size_str}",
                    "pure_label": get_quality_label(quality),
                    "ext": "mp4"
                })

        # Provide audio MP3 options with bitrates
        audio_options = []
        if has_audio:
            duration = info.get("duration", 0) or 0
            for br in ALLOWED_BITRATES:
                est_mb = round((int(br) * 1000 / 8 * duration) / (1024 * 1024), 1) if duration else 0
                size_tag = f" (~{est_mb} MB)" if est_mb > 0 else ""
                label_suffix = {
                    "128": "Standard",
                    "192": "High",
                    "256": "Very High",
                    "320": "Best"
                }.get(br, "")
                audio_options.append({
                    "quality": br,
                    "label": f"{br} kbps ({label_suffix}){size_tag}",
                    "pure_label": f"{br} kbps",
                    "ext": "mp3"
                })

        thumbnails = info.get("thumbnails", [])
        thumbnail_url = thumbnails[-1].get("url") if thumbnails else info.get("thumbnail", "")

        duration_secs = info.get("duration", 0)
        minutes, seconds = divmod(duration_secs or 0, 60)
        hours, minutes = divmod(minutes, 60)
        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}"

        response_data = {
            "success": True,
            "video_id": video_id,
            "canonical_url": canonical_url,
            "title": info.get("title", "YouTube Video"),
            "uploader": info.get("uploader", "") or info.get("channel", ""),
            "duration": duration_str,
            "duration_seconds": duration_secs,
            "thumbnail": thumbnail_url,
            "qualities": video_qualities,
            "audio_options": audio_options
        }

        # Save to metadata cache
        with metadata_cache_lock:
            metadata_cache[video_id] = {
                "timestamp": now,
                "data": response_data
            }

        return jsonify(response_data)

    except Exception as e:
        app.logger.exception("Format extraction failed")
        return jsonify({"error": clean_error(str(e))}), 500

# ============================================================
# START DOWNLOAD ROUTE
# ============================================================

@app.route("/start-download", methods=["POST"])
@app.route("/api/start-download", methods=["POST"])
def start_download():
    ip = get_client_ip()
    if not check_rate_limit(ip, "download"):
        return jsonify({"error": "Rate limit exceeded for downloads. Please wait a minute."}), 429

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON request."}), 400

    raw_url = str(data.get("url", "")).strip()
    media_type = str(data.get("type", "mp4")).lower().strip()
    quality = data.get("quality")

    if not raw_url:
        return jsonify({"error": "Please enter a YouTube link."}), 400

    video_id = extract_canonical_video_id(raw_url)
    if not video_id:
        return jsonify({"error": "Invalid or unsupported YouTube link."}), 400

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    if media_type not in ("mp4", "mp3"):
        return jsonify({"error": "Unsupported media format. Must be 'mp4' or 'mp3'."}), 400

    if media_type == "mp4":
        if quality is None:
            return jsonify({"error": "Please select a video quality."}), 400
        try:
            quality = int(quality)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid quality parameter."}), 400
        if quality not in ALLOWED_QUALITIES:
            return jsonify({"error": f"Resolution {quality}p is not supported."}), 400
    elif media_type == "mp3":
        quality = str(quality or "192").strip()
        if quality not in ALLOWED_BITRATES:
            return jsonify({"error": f"Bitrate {quality} kbps is not supported."}), 400

    # Check capacity: active + waiting
    active_count = count_jobs_by_status("downloading") + count_jobs_by_status("converting")
    waiting_count = count_jobs_by_status("waiting")

    if waiting_count >= MAX_WAITING_JOBS:
        return jsonify({
            "error": "Server is currently at maximum queue capacity. Please try again in a few minutes."
        }), 503

    # Check free disk space before queueing
    try:
        _, _, free = shutil.disk_usage(DOWNLOAD_ROOT)
        if free < 200 * 1024 * 1024:  # Less than 200MB free
            return jsonify({
                "error": "Server storage is temporarily full. Please wait for active downloads to clear."
            }), 507
    except Exception:
        pass

    download_id = str(uuid.uuid4())
    initial_status = "waiting" if active_count >= MAX_ACTIVE_DOWNLOADS else "downloading"
    now = time.time()

    with get_db() as conn:
        conn.execute("""
            INSERT INTO jobs (
                id, url, video_id, media_type, quality, status, progress, stage, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            download_id, canonical_url, video_id, media_type, str(quality),
            initial_status, 0.0,
            "Waiting in queue for an available processing slot..." if initial_status == "waiting" else "Initializing download...",
            now, now
        ))

    # Initialize cancellation event
    cancel_event = threading.Event()
    with cancellation_lock:
        cancellation_events[download_id] = cancel_event

    # Spawn background worker thread
    thread = threading.Thread(
        target=job_worker,
        args=(download_id, canonical_url, media_type, quality, cancel_event),
        daemon=True
    )
    with threads_lock:
        active_worker_threads[download_id] = thread
    thread.start()

    return jsonify({
        "success": True,
        "download_id": download_id,
        "status": initial_status,
        "message": "Job queued successfully."
    })

# ============================================================
# CANCELLATION ENDPOINT
# ============================================================

@app.route("/cancel/<download_id>", methods=["POST"])
@app.route("/api/cancel/<download_id>", methods=["POST"])
def cancel_job(download_id):
    job = get_job(download_id)
    if not job:
        return jsonify({"error": "Job ID not found."}), 404

    if job["status"] in ("completed", "failed", "cancelled"):
        return jsonify({"message": f"Job is already in {job['status']} state."}), 200

    # Signal cancellation
    with cancellation_lock:
        cancel_event = cancellation_events.get(download_id)
        if cancel_event:
            cancel_event.set()

    update_job(
        download_id,
        status="cancelled",
        stage="Job was cancelled by user.",
        error="Cancelled by user."
    )

    # Clean job files if already on disk
    job_folder = os.path.join(DOWNLOAD_ROOT, download_id)
    try:
        if os.path.exists(job_folder):
            shutil.rmtree(job_folder, ignore_errors=True)
    except Exception as e:
        app.logger.warning(f"Error removing cancelled job files: {e}")

    return jsonify({
        "success": True,
        "message": "Download cancelled successfully."
    })

# ============================================================
# JOB WORKER THREAD
# ============================================================

def job_worker(download_id: str, canonical_url: str, media_type: str, quality, cancel_event: threading.Event):
    job_folder = os.path.join(DOWNLOAD_ROOT, download_id)
    
    # 1. Wait if necessary until an active slot is available
    wait_start = time.time()
    while True:
        if cancel_event.is_set():
            return

        active_count = count_jobs_by_status("downloading") + count_jobs_by_status("converting")
        if active_count < MAX_ACTIVE_DOWNLOADS:
            break

        if time.time() - wait_start > 300:  # 5 minutes queue timeout
            update_job(
                download_id,
                status="failed",
                error="Queue timeout: server was busy for too long.",
                stage="Queue timeout"
            )
            return

        time.sleep(1.0)

    # 2. Transition to downloading
    if cancel_event.is_set():
        return

    update_job(
        download_id,
        status="downloading",
        stage="Connecting to media streams...",
        progress=0.0
    )
    os.makedirs(job_folder, exist_ok=True)

    try:
        def progress_hook(data):
            if cancel_event.is_set():
                raise Exception("Download cancelled by user.")

            status = data.get("status")
            if status == "downloading":
                downloaded = data.get("downloaded_bytes") or 0
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                percent = round((downloaded / total * 100), 1) if total else 0.0
                speed = data.get("_speed_str") or ""
                eta = data.get("_eta_str") or ""
                update_job(
                    download_id,
                    progress=percent,
                    speed=speed,
                    eta=eta,
                    stage=f"Downloading media stream ({percent}%)..."
                )
            elif status == "finished":
                update_job(
                    download_id,
                    progress=100.0,
                    status="converting",
                    stage="Merging audio & video streams with FFmpeg..." if media_type == "mp4" else "Extracting & encoding MP3 audio...",
                    speed="",
                    eta=""
                )

        outtmpl_pattern = os.path.join(job_folder, "%(title)s.%(ext)s")

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
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(quality),
                }],
            }
        else:  # mp4
            # Exact/strict target format: target height without silently lowering quality
            format_selector = (
                f"bestvideo[height={quality}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height={quality}]+bestaudio/"
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
                "continuedl": True,
                "overwrites": True
            }

        if FFMPEG_DIR:
            ydl_opts["ffmpeg_location"] = FFMPEG_DIR

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(canonical_url, download=True)
            filename = ydl.prepare_filename(info)

        if cancel_event.is_set():
            raise Exception("Download cancelled by user.")

        # Locate final generated file
        final_file = None
        target_ext = f".{media_type}"
        base_name = os.path.splitext(filename)[0]

        direct_candidate = base_name + target_ext
        if os.path.isfile(direct_candidate):
            final_file = direct_candidate
        elif os.path.isfile(filename) and filename.lower().endswith(target_ext):
            final_file = filename
        else:
            for f in os.listdir(job_folder):
                full_p = os.path.join(job_folder, f)
                if os.path.isfile(full_p) and f.lower().endswith(target_ext):
                    final_file = full_p
                    break

        if not final_file or not os.path.isfile(final_file):
            raise FileNotFoundError(f"Media extraction completed, but final {media_type.upper()} file could not be verified.")

        # Verify output file size
        filesize = os.path.getsize(final_file)
        if filesize < 1024:
            raise ValueError("Generated media file is invalid or empty (less than 1KB).")

        now = time.time()
        update_job(
            download_id,
            status="completed",
            progress=100.0,
            file_path=final_file,
            filesize=filesize,
            title=info.get("title", "YouTube Media"),
            stage="Media ready for download!",
            completed_at=now,
            speed="",
            eta=""
        )
        app.logger.info(f"Job completed successfully: {download_id} -> {final_file} ({filesize} bytes)")

    except Exception as e:
        app.logger.exception(f"Job execution failed for {download_id}")
        error_msg = clean_error(str(e))
        update_job(
            download_id,
            status="failed" if not cancel_event.is_set() else "cancelled",
            error=error_msg,
            stage="Failed: " + error_msg
        )
        # Clean folder safely on error
        try:
            if os.path.exists(job_folder):
                shutil.rmtree(job_folder, ignore_errors=True)
        except Exception:
            pass
    finally:
        with threads_lock:
            active_worker_threads.pop(download_id, None)
        with cancellation_lock:
            cancellation_events.pop(download_id, None)

# ============================================================
# PROGRESS POLLING
# ============================================================

@app.route("/progress/<download_id>", methods=["GET"])
@app.route("/api/progress/<download_id>", methods=["GET"])
def progress(download_id):
    job = get_job(download_id)
    if not job:
        return jsonify({"error": "Download ID not found."}), 404

    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "percent": job["progress"],  # backwards-compatible
        "speed": job["speed"],
        "eta": job["eta"],
        "stage": job["stage"],
        "filesize": job["filesize"],
        "title": job["title"],
        "error": job["error"]
    })

# ============================================================
# DOWNLOAD FINAL FILE (Chunked Streaming & Path Traversal Safe)
# ============================================================

@app.route("/download-file/<download_id>", methods=["GET"])
@app.route("/api/download-file/<download_id>", methods=["GET"])
def download_file(download_id):
    job = get_job(download_id)
    if not job:
        return jsonify({"error": "Download ID not found."}), 404

    if job["status"] != "completed":
        return jsonify({"error": f"Download is not ready yet (Current status: {job['status']})."}), 400

    file_path = job.get("file_path")
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Media file is missing or has expired."}), 404

    # Strict path containment verification to prevent directory traversal
    real_file_path = os.path.realpath(file_path)
    real_root = os.path.realpath(DOWNLOAD_ROOT)
    if not real_file_path.startswith(real_root):
        app.logger.error(f"Security: Path traversal attempt blocked for job {download_id}: {file_path}")
        return jsonify({"error": "Access denied."}), 403

    media_type = job.get("media_type", "mp4")
    mimetype = "audio/mpeg" if media_type == "mp3" else "video/mp4"

    # Record download start
    update_job(
        download_id,
        download_started_at=time.time(),
        download_count=job["download_count"] + 1
    )

    transfer_token = str(uuid.uuid4())
    with active_transfers_lock:
        if download_id not in active_transfers:
            active_transfers[download_id] = set()
        active_transfers[download_id].add(transfer_token)

    def generate_chunks():
        chunk_size = 64 * 1024  # 64KB chunks to prevent RAM buffering of large 4K files
        try:
            with open(real_file_path, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    yield data
        finally:
            with active_transfers_lock:
                if download_id in active_transfers:
                    active_transfers[download_id].discard(transfer_token)
                    if not active_transfers[download_id]:
                        active_transfers.pop(download_id, None)

    filename = os.path.basename(real_file_path)
    # Sanitize Content-Disposition header filename
    safe_ascii_name = re.sub(r'[^\w\s.-]', '_', filename).strip()
    encoded_filename = urllib.parse.quote(filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{encoded_filename}',
        "Content-Length": str(os.path.getsize(real_file_path)),
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "X-Content-Type-Options": "nosniff"
    }

    return Response(generate_chunks(), mimetype=mimetype, headers=headers)

# ============================================================
# STATE-AWARE BACKGROUND CLEANUP TASK
# ============================================================

def cleanup_worker():
    """
    State-aware background cleanup:
    1. NEVER deletes active jobs (waiting, downloading, converting).
    2. NEVER deletes files while an active HTTP file transfer is in progress.
    3. Respects grace periods for completed jobs.
    4. Purges failed or cancelled temporary directories promptly.
    5. Operates safely without crashing the server.
    """
    while True:
        try:
            now = time.time()
            with get_db() as conn:
                cursor = conn.execute("SELECT * FROM jobs")
                all_jobs = [dict(r) for r in cursor.fetchall()]

            for job in all_jobs:
                j_id = job["id"]
                status = job["status"]
                job_folder = os.path.join(DOWNLOAD_ROOT, j_id)

                # Skip active jobs completely
                if status in ("waiting", "downloading", "converting"):
                    continue

                # Check if there is an active HTTP transfer streaming this file
                with active_transfers_lock:
                    if j_id in active_transfers and len(active_transfers[j_id]) > 0:
                        continue

                should_delete = False

                if status == "completed":
                    # Expire after TTL or after grace period following a completed browser download
                    download_started = job.get("download_started_at")
                    completed_at = job.get("completed_at") or job.get("created_at")

                    if download_started and (now - download_started > FILE_DOWNLOAD_GRACE_PERIOD):
                        should_delete = True
                    elif now - completed_at > JOB_TTL_SECONDS:
                        should_delete = True

                elif status in ("failed", "cancelled"):
                    created_at = job.get("created_at")
                    if now - created_at > FAILED_TTL_SECONDS:
                        should_delete = True

                if should_delete:
                    try:
                        if os.path.exists(job_folder):
                            shutil.rmtree(job_folder, ignore_errors=True)
                    except Exception as err:
                        app.logger.warning(f"Cleanup rmtree error for {j_id}: {err}")

                    with get_db() as conn:
                        conn.execute("DELETE FROM jobs WHERE id = ?", (j_id,))

        except Exception as e:
            app.logger.error(f"State-aware cleanup error: {e}")

        time.sleep(60)

cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()

# ============================================================
# ENTRY POINT
# ============================================================

def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

if __name__ == "__main__":
    port = 3000
    host = "127.0.0.1"

    if is_port_in_use(host, port):
        print("=" * 65)
        print(f"[ERROR] Port {port} is already in use by another application.")
        print(f"Please stop the process using port {port} before launching,")
        print(f"or run: Get-Process -Id (Get-NetTCPConnection -LocalPort {port}).OwningProcess | Stop-Process")
        print("=" * 65)
        sys.exit(1)

    print("=" * 65)
    print(" StreamVault — YouTube to MP4 & MP3 Local Media Utility")
    print(f" Local URL: http://localhost:{port} or http://{host}:{port}")
    print(f" FFmpeg Status: {'Available (' + str(FFMPEG_DIR) + ')' if FFMPEG_AVAILABLE else 'NOT DETECTED (Audio extraction will fail)'}")
    print(f" Media Storage: {DOWNLOAD_ROOT}")
    print(" Press Ctrl+C in this terminal to stop the server.")
    print("=" * 65)

    app.run(host=host, port=port, debug=False, threaded=True)
