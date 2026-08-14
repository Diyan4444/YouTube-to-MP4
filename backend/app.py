import os
import uuid
import tempfile
import threading

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)

import yt_dlp


app = Flask(__name__)

DOWNLOAD_ROOT = os.path.join(
    tempfile.gettempdir(),
    "yt_mp4_downloads"
)

os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

downloads = {}


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# GET AVAILABLE QUALITIES
# ============================================================

@app.route("/formats", methods=["POST"])
def get_formats():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "Invalid request."
        }), 400

    video_url = data.get("url", "").strip()

    if not video_url:
        return jsonify({
            "error": "Please enter a URL."
        }), 400

    try:

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                video_url,
                download=False
            )

        formats = info.get("formats", [])

        available = {}

        for fmt in formats:

            # We only care about video formats
            height = fmt.get("height")

            if not height:
                continue

            # Only consider MP4 video
            if fmt.get("ext") != "mp4":
                continue

            # Need video codec
            if fmt.get("vcodec") == "none":
                continue

            # Prefer formats with a known resolution
            quality = height

            # Keep the best format for each resolution
            current = available.get(quality)

            if (
                current is None
                or
                (fmt.get("tbr") or 0)
                >
                (current.get("tbr") or 0)
            ):

                available[quality] = fmt

        # Desired qualities
        desired = [
            360,
            480,
            720,
            1080,
            1440,
            2160
        ]

        result = []

        for quality in desired:

            if quality in available:

                result.append({
                    "height": quality,
                    "label": get_quality_label(
                        quality
                    )
                })

        if not result:

            return jsonify({
                "error":
                    "No compatible MP4 video formats found."
            }), 400

        return jsonify({
            "title": info.get(
                "title",
                "Video"
            ),
            "qualities": result
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 400


def get_quality_label(height):

    if height == 2160:
        return "2160p (4K)"

    if height == 1440:
        return "1440p (2K)"

    if height == 1080:
        return "1080p"

    if height == 720:
        return "720p"

    if height == 480:
        return "480p"

    if height == 360:
        return "360p"

    return f"{height}p"


# ============================================================
# START DOWNLOAD
# ============================================================

@app.route(
    "/start-download",
    methods=["POST"]
)
def start_download():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "error": "Invalid request."
        }), 400


    video_url = data.get(
        "url",
        ""
    ).strip()


    quality = data.get(
        "quality"
    )


    if not video_url:

        return jsonify({
            "error":
                "Please enter a YouTube URL."
        }), 400


    if not quality:

        return jsonify({
            "error":
                "Please select a quality."
        }), 400


    try:

        quality = int(
            quality
        )

    except ValueError:

        return jsonify({
            "error":
                "Invalid quality."
        }), 400


    if quality not in [
        360,
        480,
        720,
        1080,
        1440,
        2160
    ]:

        return jsonify({
            "error":
                "Unsupported quality."
        }), 400


    download_id = str(
        uuid.uuid4()
    )


    download_folder = os.path.join(
        DOWNLOAD_ROOT,
        download_id
    )


    os.makedirs(
        download_folder,
        exist_ok=True
    )


    downloads[download_id] = {

        "status": "starting",

        "percent": 0,

        "speed": "",

        "eta": "",

        "filename": None,

        "error": None,

        "folder": download_folder

    }


    thread = threading.Thread(

        target=download_video,

        args=(
            download_id,
            video_url,
            quality,
            download_folder
        ),

        daemon=True
    )


    thread.start()


    return jsonify({

        "success": True,

        "download_id":
            download_id

    })


# ============================================================
# DOWNLOAD VIDEO
# ============================================================

def download_video(
    download_id,
    video_url,
    quality,
    download_folder
):

    def progress_hook(data):

        if data["status"] == "downloading":

            downloaded = data.get(
                "downloaded_bytes",
                0
            )

            total = (
                data.get(
                    "total_bytes"
                )
                or
                data.get(
                    "total_bytes_estimate"
                )
            )

            if total:

                percent = (
                    downloaded /
                    total
                ) * 100

            else:

                percent = 0


            downloads[
                download_id
            ][
                "status"
            ] = "downloading"


            downloads[
                download_id
            ][
                "percent"
            ] = round(
                percent,
                1
            )


            downloads[
                download_id
            ][
                "speed"
            ] = data.get(
                "_speed_str",
                ""
            )


            downloads[
                download_id
            ][
                "eta"
            ] = data.get(
                "_eta_str",
                ""
            )


        elif data["status"] == "finished":

            downloads[
                download_id
            ][
                "percent"
            ] = 100


            downloads[
                download_id
            ][
                "status"
            ] = "merging"


    try:

        # ====================================================
        # QUALITY FORMAT
        # ====================================================

        format_selector = (
            f"bestvideo[height<={quality}]"
            "[ext=mp4]"
            "+"
            "bestaudio[ext=m4a]"
            "/"
            f"best[height<={quality}]"
            "[ext=mp4]"
            "/"
            f"best[height<={quality}]"
        )


        ydl_opts = {

            "format":
                format_selector,

            "merge_output_format":
                "mp4",

            "outtmpl":
                os.path.join(
                    download_folder,
                    "%(title)s.%(ext)s"
                ),

            "noplaylist":
                True,

            "quiet":
                True,

            "no_warnings":
                True,

            "retries":
                3,

            "fragment_retries":
                3,

            "progress_hooks":
                [
                    progress_hook
                ]
        }


        # ====================================================
        # DOWNLOAD
        # ====================================================

        with yt_dlp.YoutubeDL(
            ydl_opts
        ) as ydl:

            info = ydl.extract_info(
                video_url,
                download=True
            )


            filename = ydl.prepare_filename(
                info
            )


            base_name = os.path.splitext(
                filename
            )[0]


            possible_files = [

                base_name + ".mp4",

                filename

            ]


            final_file = None


            for path in possible_files:

                if os.path.isfile(path):

                    final_file = path

                    break


            # Fallback search

            if final_file is None:

                for file in os.listdir(
                    download_folder
                ):

                    full_path = os.path.join(
                        download_folder,
                        file
                    )


                    if (
                        os.path.isfile(
                            full_path
                        )
                        and
                        file.lower().endswith(
                            ".mp4"
                        )
                    ):

                        final_file = full_path

                        break


            if final_file is None:

                raise FileNotFoundError(
                    "Final MP4 file was not found."
                )


        # ====================================================
        # SUCCESS
        # ====================================================

        downloads[
            download_id
        ][
            "status"
        ] = "completed"


        downloads[
            download_id
        ][
            "percent"
        ] = 100


        downloads[
            download_id
        ][
            "filename"
        ] = final_file


    except Exception as e:

        print(
            "Download error:",
            e
        )


        downloads[
            download_id
        ][
            "status"
        ] = "error"


        downloads[
            download_id
        ][
            "error"
        ] = str(e)


# ============================================================
# PROGRESS
# ============================================================

@app.route(
    "/progress/<download_id>"
)
def progress(download_id):

    download = downloads.get(
        download_id
    )


    if not download:

        return jsonify({
            "error":
                "Download not found."
        }), 404


    return jsonify({

        "status":
            download["status"],

        "percent":
            download["percent"],

        "speed":
            download["speed"],

        "eta":
            download["eta"],

        "error":
            download["error"]

    })


# ============================================================
# DOWNLOAD FINAL FILE
# ============================================================

@app.route(
    "/download-file/<download_id>"
)
def download_file(download_id):

    download = downloads.get(
        download_id
    )


    if not download:

        return jsonify({
            "error":
                "Download not found."
        }), 404


    if download["status"] != "completed":

        return jsonify({
            "error":
                "Download isn't completed."
        }), 400


    file_path = download[
        "filename"
    ]


    if not file_path:

        return jsonify({
            "error":
                "File not found."
        }), 404


    if not os.path.exists(
        file_path
    ):

        return jsonify({
            "error":
                "File no longer exists."
        }), 404


    return send_file(

        file_path,

        as_attachment=True,

        download_name=os.path.basename(
            file_path
        ),

        mimetype="video/mp4"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )