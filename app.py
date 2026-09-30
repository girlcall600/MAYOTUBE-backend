import os
import re
import json
import base64
import tempfile
import traceback
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

import yt_dlp


# ============================================================
# MAYOTUBE BACKEND
# ============================================================

app = Flask(__name__)
CORS(app)

APP_NAME = "MAYOTUBE API"
APP_VERSION = "4.0"

YOUTUBE_BASE = "https://www.youtube.com"

DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 50

COOKIE_FILE = None


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    try:
        return str(value).strip()
    except Exception:
        return ""


def safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(value)

    except Exception:
        return default


def safe_float(value, default=0):
    try:
        if value is None:
            return default

        return float(value)

    except Exception:
        return default


def is_youtube_url(url):
    url = clean_text(url).lower()

    if not url:
        return False

    return (
        "youtube.com" in url
        or "youtu.be" in url
        or "youtube-nocookie.com" in url
    )


def extract_youtube_video_id(url):
    url = clean_text(url)

    if not url:
        return None

    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/live/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


def is_bot_error(error_text):
    text = clean_text(error_text).lower()

    indicators = [
        "sign in to confirm",
        "you're not a bot",
        "you’re not a bot",
        "not a bot",
        "confirm you're not a bot",
        "confirm you’re not a bot",
        "use --cookies-from-browser",
        "cookies-from-browser",
        "login_required",
        "po token",
        "p.o. token",
        "botguard",
        "droidguard",
        "http error 403",
        "forbidden",
    ]

    return any(item in text for item in indicators)


# ============================================================
# OPTIONAL YOUTUBE COOKIES
# ============================================================

def prepare_cookie_file():
    """
    Optional:
    Set Vercel Environment Variable:

        YOUTUBE_COOKIES_B64

    with a base64 encoded Netscape cookies.txt file.

    Nothing is required if the variable is absent.
    """

    global COOKIE_FILE

    if COOKIE_FILE and os.path.exists(COOKIE_FILE):
        return COOKIE_FILE

    encoded = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()

    if not encoded:
        return None

    try:
        decoded = base64.b64decode(encoded)

        temp_path = os.path.join(
            tempfile.gettempdir(),
            "mayotube_youtube_cookies.txt"
        )

        with open(temp_path, "wb") as file:
            file.write(decoded)

        COOKIE_FILE = temp_path

        return COOKIE_FILE

    except Exception:
        COOKIE_FILE = None
        return None


# ============================================================
# OPTIONAL PO TOKEN
# ============================================================

def get_po_token():
    """
    Optional environment variable.

    Example format supported by yt-dlp:

        mweb.gvs+TOKEN

    or another extractor-argument value supported
    by the installed yt-dlp version.
    """

    return os.environ.get("YOUTUBE_PO_TOKEN", "").strip()


# ============================================================
# YT-DLP OPTIONS
# ============================================================

def build_ydl_options(
    player_clients=None,
    download=False,
    quiet=True,
    no_warnings=True
):
    options = {
        "quiet": quiet,
        "no_warnings": no_warnings,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "geo_bypass": True,
        "geo_bypass_country": "PK",

        "socket_timeout": 25,

        "retries": 2,
        "fragment_retries": 2,

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        "extractor_args": {
            "youtube": {}
        },
    }

    if download:
        options["noplaylist"] = True

    # --------------------------------------------------------
    # YouTube client selection
    # --------------------------------------------------------

    if player_clients:
        options["extractor_args"]["youtube"]["player_client"] = (
            player_clients
        )

    # --------------------------------------------------------
    # Optional PO token
    # --------------------------------------------------------

    po_token = get_po_token()

    if po_token:
        options["extractor_args"]["youtube"]["po_token"] = po_token

    # --------------------------------------------------------
    # Optional cookies
    # --------------------------------------------------------

    cookie_file = prepare_cookie_file()

    if cookie_file:
        options["cookiefile"] = cookie_file

    return options


# ============================================================
# YOUTUBE EXTRACTION
# ============================================================

def extract_info_with_fallback(url, download=False):
    """
    Try several YouTube clients.

    Important:
    No single client is guaranteed to work for every YouTube
    video because YouTube changes its anti-bot requirements.
    """

    url = clean_text(url)

    if not url:
        raise Exception("URL is required")

    # --------------------------------------------------------
    # For non-YouTube URLs
    # --------------------------------------------------------

    if not is_youtube_url(url):

        options = build_ydl_options(
            player_clients=None,
            download=download
        )

        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(
                url,
                download=download
            )

    # --------------------------------------------------------
    # Current fallback order
    #
    # android_vr:
    #     currently documented by yt-dlp as not requiring PO
    #     token for GVS.
    #
    # tv:
    #     currently documented as not requiring PO token,
    #     although availability/DRM can vary.
    #
    # web_embedded:
    #     only works for embeddable videos.
    #
    # web_safari:
    #     can expose HLS in some cases.
    #
    # default:
    #     normal yt-dlp extraction.
    # --------------------------------------------------------

    client_attempts = [
        ["android_vr"],
        ["tv"],
        ["web_embedded"],
        ["web_safari"],
        ["ios"],
        None,
    ]

    errors = []

    for clients in client_attempts:

        try:

            options = build_ydl_options(
                player_clients=clients,
                download=download
            )

            with yt_dlp.YoutubeDL(options) as ydl:

                info = ydl.extract_info(
                    url,
                    download=download
                )

                if info:
                    return info

        except Exception as error:

            message = clean_text(error)

            errors.append({
                "clients": clients,
                "error": message
            })

            # Continue to next client.

    # --------------------------------------------------------
    # Nothing worked
    # --------------------------------------------------------

    last_error = (
        errors[-1]["error"]
        if errors
        else "Unknown YouTube extraction error"
    )

    combined = "\n".join(
        [
            "client="
            + str(item["clients"])
            + " -> "
            + item["error"]
            for item in errors
        ]
    )

    if is_bot_error(combined):

        raise Exception(
            "YouTube blocked this server request. "
            "The available yt-dlp clients were tried, but "
            "YouTube requires additional verification, cookies, "
            "or a PO Token for this request. "
            "Last error: "
            + last_error
        )

    raise Exception(last_error)


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_filesize(value):
    value = safe_int(value, 0)

    if value <= 0:
        return None

    if value < 1024 * 1024:
        return f"{round(value / 1024)} KB"

    if value < 1024 * 1024 * 1024:
        return f"{round(value / (1024 * 1024), 1)} MB"

    return f"{round(value / (1024 * 1024 * 1024), 2)} GB"


def format_resolution(width, height):
    width = safe_int(width, 0)
    height = safe_int(height, 0)

    if width > 0 and height > 0:
        return f"{width}x{height}"

    if height > 0:
        return f"{height}p"

    return ""


def codec_name(codec):
    codec = clean_text(codec)

    if not codec:
        return ""

    return codec


def build_format_item(fmt):
    if not fmt:
        return None

    url = fmt.get("url")

    if not url:
        return None

    width = safe_int(fmt.get("width"), 0)
    height = safe_int(fmt.get("height"), 0)

    vcodec = codec_name(fmt.get("vcodec"))
    acodec = codec_name(fmt.get("acodec"))

    if vcodec and vcodec != "none":
        if acodec and acodec != "none":
            kind = "video+audio"
        else:
            kind = "video"
    elif acodec and acodec != "none":
        kind = "audio"
    else:
        return None

    ext = clean_text(fmt.get("ext"))

    filesize = (
        fmt.get("filesize")
        or fmt.get("filesize_approx")
        or 0
    )

    return {
        "format_id": clean_text(fmt.get("format_id")),
        "url": url,
        "ext": ext,
        "height": height,
        "width": width,
        "fps": safe_float(fmt.get("fps"), 0),
        "filesize": safe_int(filesize, 0),
        "filesize_text": format_filesize(filesize),
        "vcodec": vcodec,
        "acodec": acodec,
        "kind": kind,
        "quality": clean_text(fmt.get("format_note")),
        "format_note": clean_text(fmt.get("format_note")),
        "resolution": format_resolution(width, height),
        "tbr": safe_float(fmt.get("tbr"), 0),
        "abr": safe_float(fmt.get("abr"), 0),
    }


def extract_formats(info):
    formats = info.get("formats") or []

    qualities = []
    audio = []

    for fmt in formats:

        item = build_format_item(fmt)

        if not item:
            continue

        if item["kind"] == "audio":
            audio.append(item)
        else:
            qualities.append(item)

    # --------------------------------------------------------
    # Sort video qualities
    # --------------------------------------------------------

    qualities.sort(
        key=lambda item: (
            item.get("height", 0),
            item.get("width", 0),
            item.get("tbr", 0),
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # Sort audio qualities
    # --------------------------------------------------------

    audio.sort(
        key=lambda item: (
            item.get("abr", 0),
            item.get("tbr", 0),
            item.get("filesize", 0),
        ),
        reverse=True
    )

    return qualities, audio


def get_best_thumbnail(info):
    thumbnails = info.get("thumbnails") or []

    if thumbnails:

        valid = [
            item
            for item in thumbnails
            if item.get("url")
        ]

        if valid:
            valid.sort(
                key=lambda item: (
                    safe_int(item.get("width"), 0)
                    * safe_int(item.get("height"), 0)
                ),
                reverse=True
            )

            return valid[0].get("url")

    return info.get("thumbnail")


def build_video_data(info):
    qualities, audio = extract_formats(info)

    video_id = (
        clean_text(info.get("id"))
        or extract_youtube_video_id(info.get("webpage_url"))
    )

    return {
        "id": video_id,
        "title": clean_text(info.get("title")),
        "description": clean_text(info.get("description")),
        "thumbnail": get_best_thumbnail(info),
        "channel": clean_text(
            info.get("channel")
            or info.get("uploader")
            or info.get("uploader_id")
        ),
        "uploader": clean_text(info.get("uploader")),
        "duration": safe_int(info.get("duration"), 0),
        "view_count": safe_int(info.get("view_count"), 0),
        "like_count": safe_int(info.get("like_count"), 0),
        "upload_date": clean_text(info.get("upload_date")),
        "webpage_url": clean_text(info.get("webpage_url")),
        "original_url": clean_text(info.get("original_url")),
        "qualities": qualities,
        "audio": audio,
    }


# ============================================================
# API: VIDEO INFO
# ============================================================

@app.route("/api/video-info", methods=["GET", "POST"])
def api_video_info():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            url = clean_text(
                body.get("url")
            )

        else:

            url = clean_text(
                request.args.get("url")
            )

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        data = build_video_data(info)

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error)
        }), 500


# ============================================================
# API: DOWNLOAD LINKS
# ============================================================

@app.route("/api/download-links", methods=["GET", "POST"])
def api_download_links():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            url = clean_text(
                body.get("url")
            )

        else:

            url = clean_text(
                request.args.get("url")
            )

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        video_data = build_video_data(info)

        return jsonify({
            "success": True,
            "data": video_data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error)
        }), 500


# ============================================================
# API: DOWNLOAD
# ============================================================

@app.route("/api/download", methods=["GET", "POST"])
def api_download():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            url = clean_text(
                body.get("url")
            )

        else:

            url = clean_text(
                request.args.get("url")
            )

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        data = build_video_data(info)

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error)
        }), 500


# ============================================================
# SEARCH RESULT FORMATTER
# ============================================================

def build_search_item(item):

    if not item:
        return None

    video_id = clean_text(
        item.get("id")
    )

    if not video_id:
        return None

    item_type = clean_text(
        item.get("_type")
        or item.get("ie_key")
        or item.get("type")
    )

    title = clean_text(
        item.get("title")
    )

    thumbnail = (
        item.get("thumbnail")
        or item.get("thumbnails", [{}])[0].get("url")
        if item.get("thumbnails")
        else item.get("thumbnail")
    )

    webpage_url = clean_text(
        item.get("webpage_url")
        or item.get("url")
    )

    if not webpage_url and len(video_id) == 11:
        webpage_url = (
            "https://www.youtube.com/watch?v="
            + video_id
        )

    return {
        "id": video_id,
        "videoId": video_id if len(video_id) == 11 else "",
        "title": title,
        "thumbnail": thumbnail,
        "channel": clean_text(
            item.get("channel")
            or item.get("uploader")
        ),
        "uploader": clean_text(
            item.get("uploader")
        ),
        "duration": safe_int(
            item.get("duration"),
            0
        ),
        "view_count": safe_int(
            item.get("view_count"),
            0
        ),
        "webpage_url": webpage_url,
        "url": webpage_url,
        "type": item_type,
    }


# ============================================================
# API: SEARCH
# ============================================================

@app.route("/api/search", methods=["GET", "POST"])
def api_search():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            query = clean_text(
                body.get("query")
            )

            requested_limit = safe_int(
                body.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

            search_type = clean_text(
                body.get("type")
                or "video"
            )

        else:

            query = clean_text(
                request.args.get("q")
                or request.args.get("query")
            )

            requested_limit = safe_int(
                request.args.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

            search_type = clean_text(
                request.args.get("type")
                or "video"
            )

        if not query:

            return jsonify({
                "success": False,
                "error": "Search query is required"
            }), 400

        limit = max(
            1,
            min(
                requested_limit,
                MAX_SEARCH_LIMIT
            )
        )

        if search_type not in [
            "video",
            "channel",
            "playlist"
        ]:
            search_type = "video"

        search_prefix = "ytsearch"

        if search_type == "channel":
            search_prefix = "ytsearch"

        elif search_type == "playlist":
            search_prefix = "ytsearch"

        search_query = (
            f"{search_prefix}{limit}:{query}"
        )

        options = build_ydl_options(
            player_clients=None,
            download=False
        )

        options["extract_flat"] = True

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                search_query,
                download=False
            )

        entries = (
            info.get("entries")
            if info
            else []
        )

        results = []

        for entry in entries or []:

            item = build_search_item(
                entry
            )

            if not item:
                continue

            # ------------------------------------------------
            # Filter requested type where possible
            # ------------------------------------------------

            if search_type == "channel":

                entry_type = clean_text(
                    entry.get("_type")
                ).lower()

                if (
                    entry_type
                    and entry_type not in [
                        "url",
                        "channel"
                    ]
                ):
                    continue

            results.append(item)

            if len(results) >= limit:
                break

        return jsonify({
            "success": True,
            "query": query,
            "count": len(results),
            "results": results,
            "continuation": None,
            "has_more": False,
            "requested_limit": limit
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error),
            "query": query if "query" in locals() else ""
        }), 500


# ============================================================
# API: SHORTS
# ============================================================

@app.route("/api/shorts", methods=["GET", "POST"])
def api_shorts():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            query = clean_text(
                body.get("query")
                or body.get("q")
                or "YouTube Shorts"
            )

            requested_limit = safe_int(
                body.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

        else:

            query = clean_text(
                request.args.get("q")
                or request.args.get("query")
                or "YouTube Shorts"
            )

            requested_limit = safe_int(
                request.args.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

        limit = max(
            1,
            min(
                requested_limit,
                MAX_SEARCH_LIMIT
            )
        )

        search_query = (
            f"ytsearch{limit}:{query} shorts"
        )

        options = build_ydl_options(
            player_clients=None,
            download=False
        )

        options["extract_flat"] = True

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                search_query,
                download=False
            )

        entries = (
            info.get("entries")
            if info
            else []
        )

        results = []

        for entry in entries or []:

            item = build_search_item(
                entry
            )

            if not item:
                continue

            results.append(item)

            if len(results) >= limit:
                break

        return jsonify({
            "success": True,
            "query": query,
            "count": len(results),
            "results": results,
            "continuation": None,
            "has_more": False,
            "requested_limit": limit
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error)
        }), 500


# ============================================================
# OLD COMPATIBILITY ENDPOINT
# ============================================================

@app.route("/search", methods=["GET", "POST"])
def old_search():

    try:

        if request.method == "POST":

            body = request.get_json(
                silent=True
            ) or {}

            query = clean_text(
                body.get("q")
                or body.get("query")
            )

            limit = safe_int(
                body.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

        else:

            query = clean_text(
                request.args.get("q")
                or request.args.get("query")
            )

            limit = safe_int(
                request.args.get("limit"),
                DEFAULT_SEARCH_LIMIT
            )

        if not query:

            return jsonify({
                "success": False,
                "error": "Search query is required"
            }), 400

        limit = max(
            1,
            min(
                limit,
                MAX_SEARCH_LIMIT
            )
        )

        options = build_ydl_options()

        options["extract_flat"] = True

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False
            )

        entries = (
            info.get("entries")
            if info
            else []
        )

        results = []

        for entry in entries or []:

            item = build_search_item(
                entry
            )

            if item:
                results.append(item)

        return jsonify({
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(error)
        }), 500


# ============================================================
# OLD DOWNLOAD-LINKS COMPATIBILITY ENDPOINT
# ============================================================

@app.route("/get-download-links", methods=["GET", "POST"])
def old_download_links():

    return api_download_links()


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "running",
        "service": APP_NAME,
        "version": APP_VERSION,
        "backend": "Vercel",
        "youtube_extractor": "yt-dlp",
        "search_limit": MAX_SEARCH_LIMIT,
        "cookies_configured": bool(
            os.environ.get(
                "YOUTUBE_COOKIES_B64",
                ""
            ).strip()
        ),
        "po_token_configured": bool(
            os.environ.get(
                "YOUTUBE_PO_TOKEN",
                ""
            ).strip()
        )
    })


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "success": True,
        "name": APP_NAME,
        "version": APP_VERSION,
        "status": "running",
        "backend": "Vercel",
        "features": [
            "youtube-video-info",
            "youtube-download-links",
            "youtube-search",
            "youtube-shorts",
            "multiple-youtube-clients",
            "optional-youtube-cookies",
            "optional-youtube-po-token",
            "50-results-per-request"
        ],
        "endpoints": {
            "health": "/health",
            "video_info": "/api/video-info",
            "download_links": "/api/download-links",
            "download": "/api/download",
            "search": "/api/search",
            "shorts": "/api/shorts",
            "old_search": "/search",
            "old_download_links": "/get-download-links"
        }
    })


# ============================================================
# VERCEL / LOCAL ENTRY
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
