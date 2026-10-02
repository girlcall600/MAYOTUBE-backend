import os
import re
import json
import base64
import tempfile
import traceback
import uuid
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS

import yt_dlp

try:
    from vercel.blob import BlobClient
except Exception:
    BlobClient = None


# ============================================================
# MAYOTUBE BACKEND
# POWER / FUTURE-READY VERSION
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# ADMIN PANEL
# ============================================================

@app.route(
    "/admin",
    methods=["GET"]
)
def admin_panel():
    return render_template("admin.html")

APP_NAME = "MAYOTUBE API"
APP_VERSION = "5.1"

YOUTUBE_BASE = "https://www.youtube.com"

DEFAULT_SEARCH_LIMIT = 50
MAX_SEARCH_LIMIT = 50

COOKIE_FILE = None


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

BGUTIL_PROVIDER_URL = (
    os.environ.get(
        "BGUTIL_PROVIDER_URL",
        ""
    )
    .strip()
    .rstrip("/")
)


BGUTIL_ENABLED = (
    os.environ.get(
        "BGUTIL_ENABLED",
        "true"
    ).strip().lower()
    not in [
        "0",
        "false",
        "no",
        "off"
    ]
)


YOUTUBE_PO_TOKEN = (
    os.environ.get(
        "YOUTUBE_PO_TOKEN",
        ""
    ).strip()
)


YOUTUBE_COOKIES_B64 = (
    os.environ.get(
        "YOUTUBE_COOKIES_B64",
        ""
    ).strip()
)


# ============================================================
# ADMIN CMS CONFIGURATION
# ============================================================

ADMIN_TOKEN = (
    os.environ.get(
        "MAYOTUBE_ADMIN_TOKEN",
        ""
    ).strip()
)


BLOB_TOKEN = (
    os.environ.get(
        "BLOB_READ_WRITE_TOKEN",
        ""
    ).strip()
)


CMS_CONTENT_PATH = (
    os.environ.get(
        "MAYOTUBE_CMS_CONTENT_PATH",
        "mayotube/cms/content.json"
    ).strip()
)


CMS_MEDIA_PREFIX = (
    os.environ.get(
        "MAYOTUBE_CMS_MEDIA_PREFIX",
        "mayotube/media"
    ).strip().strip("/")
)




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


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def generate_id(prefix="item"):
    return (
        prefix
        + "_"
        + uuid.uuid4().hex
    )


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

        match = re.search(
            pattern,
            url
        )

        if match:
            return match.group(1)

    return None


def is_bot_error(error_text):
    text = clean_text(
        error_text
    ).lower()

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
        "verification required",
        "automated requests",
        "unusual traffic",
        "sabr",
    ]

    return any(
        item in text
        for item in indicators
    )


# ============================================================
# OPTIONAL YOUTUBE COOKIES
# ============================================================

def prepare_cookie_file():

    global COOKIE_FILE

    if (
        COOKIE_FILE
        and os.path.exists(COOKIE_FILE)
    ):
        return COOKIE_FILE

    encoded = os.environ.get(
        "YOUTUBE_COOKIES_B64",
        ""
    ).strip()

    if not encoded:
        return None

    try:

        decoded = base64.b64decode(
            encoded
        )

        temp_path = os.path.join(
            tempfile.gettempdir(),
            "mayotube_youtube_cookies.txt"
        )

        with open(
            temp_path,
            "wb"
        ) as file:

            file.write(
                decoded
            )

        COOKIE_FILE = temp_path

        return COOKIE_FILE

    except Exception:

        COOKIE_FILE = None

        return None


# ============================================================
# OPTIONAL MANUAL PO TOKEN
# ============================================================

def get_po_token():

    return os.environ.get(
        "YOUTUBE_PO_TOKEN",
        ""
    ).strip()


# ============================================================
# PO PROVIDER STATUS
# ============================================================

def is_bgutil_configured():

    return bool(
        BGUTIL_ENABLED
        and BGUTIL_PROVIDER_URL
    )


def get_provider_status():

    if not BGUTIL_ENABLED:

        return {
            "enabled": False,
            "configured": False,
            "url_configured": False,
            "mode": "disabled"
        }

    if not BGUTIL_PROVIDER_URL:

        return {
            "enabled": True,
            "configured": False,
            "url_configured": False,
            "mode": "fallback-only"
        }

    return {
        "enabled": True,
        "configured": True,
        "url_configured": True,
        "mode": "bgutil-http",
        "base_url": BGUTIL_PROVIDER_URL
    }


# ============================================================
# YT-DLP EXTRACTOR ARGUMENTS
# ============================================================

def build_extractor_args(
    player_clients=None
):

    extractor_args = {
        "youtube": {}
    }

    if is_bgutil_configured():

        extractor_args[
            "youtubepot-bgutilhttp"
        ] = {
            "base_url": [
                BGUTIL_PROVIDER_URL
            ]
        }

    if player_clients:

        extractor_args[
            "youtube"
        ][
            "player_client"
        ] = player_clients

    po_token = get_po_token()

    if po_token:

        extractor_args[
            "youtube"
        ][
            "po_token"
        ] = [
            po_token
        ]

    return extractor_args


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
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 "
                "Safari/537.36"
            ),

            "Accept-Language":
                "en-US,en;q=0.9",

        },

        "extractor_args":
            build_extractor_args(
                player_clients
            ),
    }

    if download:

        options[
            "noplaylist"
        ] = True

    cookie_file = (
        prepare_cookie_file()
    )

    if cookie_file:

        options[
            "cookiefile"
        ] = cookie_file

    return options


# ============================================================
# YOUTUBE CLIENT STRATEGY
# ============================================================

def get_youtube_client_attempts():

    attempts = []

    if is_bgutil_configured():

        attempts.extend([
            ["mweb"],
            ["mweb", "web"],
            ["mweb", "web_safari"],
            ["web_safari"],
        ])

    attempts.extend([
        ["android_vr"],
        ["tv"],
        ["web_embedded"],
        ["web_safari"],
        ["ios"],
        None,
    ])

    unique = []

    for item in attempts:

        if item not in unique:

            unique.append(item)

    return unique


# ============================================================
# YOUTUBE EXTRACTION
# ============================================================

def extract_info_with_fallback(
    url,
    download=False
):

    url = clean_text(url)

    if not url:

        raise Exception(
            "URL is required"
        )

    if not is_youtube_url(url):

        options = build_ydl_options(
            player_clients=None,
            download=download
        )

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            return ydl.extract_info(
                url,
                download=download
            )

    client_attempts = (
        get_youtube_client_attempts()
    )

    errors = []

    for clients in client_attempts:

        try:

            options = build_ydl_options(
                player_clients=clients,
                download=download
            )

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    url,
                    download=download
                )

                if info:

                    return info

        except Exception as error:

            message = clean_text(
                error
            )

            errors.append({
                "clients": clients,
                "error": message
            })

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

    if is_bot_error(
        combined
    ):

        if not is_bgutil_configured():

            raise Exception(
                "YouTube blocked this server request. "
                "The current yt-dlp fallback clients were "
                "tried, but this server needs a PO Token "
                "provider or valid YouTube cookies. "
                "BGUTIL_PROVIDER_URL is not configured. "
                "Last error: "
                + last_error
            )

        raise Exception(
            "YouTube extraction failed even with the "
            "configured PO Token provider. "
            "Check the provider URL, provider service "
            "availability, yt-dlp plugin installation, "
            "and YouTube client configuration. "
            "Last error: "
            + last_error
        )

    raise Exception(
        last_error
    )


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_filesize(value):

    value = safe_int(
        value,
        0
    )

    if value <= 0:
        return None

    if value < 1024 * 1024:

        return (
            f"{round(value / 1024)} KB"
        )

    if value < 1024 * 1024 * 1024:

        return (
            f"{round(value / (1024 * 1024), 1)} MB"
        )

    return (
        f"{round(value / (1024 * 1024 * 1024), 2)} GB"
    )


def format_resolution(
    width,
    height
):

    width = safe_int(
        width,
        0
    )

    height = safe_int(
        height,
        0
    )

    if (
        width > 0
        and height > 0
    ):

        return (
            f"{width}x{height}"
        )

    if height > 0:

        return (
            f"{height}p"
        )

    return ""


def codec_name(codec):

    codec = clean_text(
        codec
    )

    if not codec:
        return ""

    return codec


def build_format_item(fmt):

    if not fmt:
        return None

    url = fmt.get(
        "url"
    )

    if not url:
        return None

    width = safe_int(
        fmt.get("width"),
        0
    )

    height = safe_int(
        fmt.get("height"),
        0
    )

    vcodec = codec_name(
        fmt.get("vcodec")
    )

    acodec = codec_name(
        fmt.get("acodec")
    )

    if (
        vcodec
        and vcodec != "none"
    ):

        if (
            acodec
            and acodec != "none"
        ):

            kind = "video+audio"

        else:

            kind = "video"

    elif (
        acodec
        and acodec != "none"
    ):

        kind = "audio"

    else:

        return None

    ext = clean_text(
        fmt.get("ext")
    )

    filesize = (
        fmt.get("filesize")
        or fmt.get("filesize_approx")
        or 0
    )

    return {

        "format_id":
            clean_text(
                fmt.get("format_id")
            ),

        "url":
            url,

        "ext":
            ext,

        "height":
            height,

        "width":
            width,

        "fps":
            safe_float(
                fmt.get("fps"),
                0
            ),

        "filesize":
            safe_int(
                filesize,
                0
            ),

        "filesize_text":
            format_filesize(
                filesize
            ),

        "vcodec":
            vcodec,

        "acodec":
            acodec,

        "kind":
            kind,

        "quality":
            clean_text(
                fmt.get("format_note")
            ),

        "format_note":
            clean_text(
                fmt.get("format_note")
            ),

        "resolution":
            format_resolution(
                width,
                height
            ),

        "tbr":
            safe_float(
                fmt.get("tbr"),
                0
            ),

        "abr":
            safe_float(
                fmt.get("abr"),
                0
            ),
    }


def extract_formats(info):

    formats = (
        info.get("formats")
        or []
    )

    qualities = []

    audio = []

    for fmt in formats:

        item = build_format_item(
            fmt
        )

        if not item:
            continue

        if (
            item["kind"]
            == "audio"
        ):

            audio.append(
                item
            )

        else:

            qualities.append(
                item
            )

    qualities.sort(
        key=lambda item: (
            item.get(
                "height",
                0
            ),
            item.get(
                "width",
                0
            ),
            item.get(
                "tbr",
                0
            ),
        ),
        reverse=True
    )

    audio.sort(
        key=lambda item: (
            item.get(
                "abr",
                0
            ),
            item.get(
                "tbr",
                0
            ),
            item.get(
                "filesize",
                0
            ),
        ),
        reverse=True
    )

    return (
        qualities,
        audio
    )


def get_best_thumbnail(info):

    thumbnails = (
        info.get("thumbnails")
        or []
    )

    if thumbnails:

        valid = [
            item
            for item in thumbnails
            if item.get("url")
        ]

        if valid:

            valid.sort(
                key=lambda item: (
                    safe_int(
                        item.get(
                            "width"
                        ),
                        0
                    )
                    *
                    safe_int(
                        item.get(
                            "height"
                        ),
                        0
                    )
                ),
                reverse=True
            )

            return valid[0].get(
                "url"
            )

    return info.get(
        "thumbnail"
    )


def build_video_data(info):

    qualities, audio = (
        extract_formats(
            info
        )
    )

    video_id = (
        clean_text(
            info.get("id")
        )
        or extract_youtube_video_id(
            info.get(
                "webpage_url"
            )
        )
    )

    return {

        "id":
            video_id,

        "title":
            clean_text(
                info.get("title")
            ),

        "description":
            clean_text(
                info.get("description")
            ),

        "thumbnail":
            get_best_thumbnail(
                info
            ),

        "channel":
            clean_text(
                info.get("channel")
                or info.get("uploader")
                or info.get("uploader_id")
            ),

        "uploader":
            clean_text(
                info.get("uploader")
            ),

        "duration":
            safe_int(
                info.get("duration"),
                0
            ),

        "view_count":
            safe_int(
                info.get("view_count"),
                0
            ),

        "like_count":
            safe_int(
                info.get("like_count"),
                0
            ),

        "upload_date":
            clean_text(
                info.get("upload_date")
            ),

        "webpage_url":
            clean_text(
                info.get("webpage_url")
            ),

        "original_url":
            clean_text(
                info.get("original_url")
            ),

        "qualities":
            qualities,

        "audio":
            audio,

    }


# ============================================================
# REQUEST URL HELPER
# ============================================================

def get_request_url():

    if request.method == "POST":

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        return clean_text(
            body.get("url")
        )

    return clean_text(
        request.args.get(
            "url"
        )
    )


# ============================================================
# API: VIDEO INFO
# ============================================================

@app.route(
    "/api/video-info",
    methods=["GET", "POST"]
)
def api_video_info():

    try:

        url = get_request_url()

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        data = build_video_data(
            info
        )

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(
                error
            )
        }), 500


# ============================================================
# API: DOWNLOAD LINKS
# ============================================================

@app.route(
    "/api/download-links",
    methods=["GET", "POST"]
)
def api_download_links():

    try:

        url = get_request_url()

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        video_data = build_video_data(
            info
        )

        return jsonify({
            "success": True,
            "data": video_data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(
                error
            )
        }), 500


# ============================================================
# API: DOWNLOAD
# ============================================================

@app.route(
    "/api/download",
    methods=["GET", "POST"]
)
def api_download():

    try:

        url = get_request_url()

        if not url:

            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400

        info = extract_info_with_fallback(
            url,
            download=False
        )

        data = build_video_data(
            info
        )

        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "error": clean_text(
                error
            )
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

    thumbnails = (
        item.get("thumbnails")
        or []
    )

    thumbnail = (
        item.get("thumbnail")
    )

    if (
        not thumbnail
        and thumbnails
    ):

        thumbnail = (
            thumbnails[0].get("url")
        )

    webpage_url = clean_text(
        item.get("webpage_url")
        or item.get("url")
    )

    if (
        not webpage_url
        and len(video_id) == 11
    ):

        webpage_url = (
            "https://www.youtube.com/watch?v="
            + video_id
        )

    return {

        "id":
            video_id,

        "videoId":
            video_id
            if len(video_id) == 11
            else "",

        "title":
            title,

        "thumbnail":
            thumbnail,

        "channel":
            clean_text(
                item.get("channel")
                or item.get("uploader")
            ),

        "uploader":
            clean_text(
                item.get("uploader")
            ),

        "duration":
            safe_int(
                item.get("duration"),
                0
            ),

        "view_count":
            safe_int(
                item.get("view_count"),
                0
            ),

        "webpage_url":
            webpage_url,

        "url":
            webpage_url,

        "type":
            item_type,

    }


# ============================================================
# SEARCH OPTIONS
# ============================================================

def build_search_options():

    options = build_ydl_options(
        player_clients=None,
        download=False
    )

    options[
        "extract_flat"
    ] = True

    return options


# ============================================================
# API: SEARCH
# ============================================================

@app.route(
    "/api/search",
    methods=["GET", "POST"]
)
def api_search():

    query = ""

    try:

        if request.method == "POST":

            body = (
                request.get_json(
                    silent=True
                )
                or {}
            )

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
                "error":
                    "Search query is required"
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

        search_query = (
            f"ytsearch{limit}:{query}"
        )

        options = build_search_options()

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

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

        for entry in (
            entries or []
        ):

            item = build_search_item(
                entry
            )

            if not item:
                continue

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

            results.append(
                item
            )

            if len(results) >= limit:

                break

        return jsonify({

            "success":
                True,

            "query":
                query,

            "count":
                len(results),

            "results":
                results,

            "continuation":
                None,

            "has_more":
                False,

            "requested_limit":
                limit,

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                ),

            "query":
                query,

        }), 500


# ============================================================
# API: SHORTS
# ============================================================

@app.route(
    "/api/shorts",
    methods=["GET", "POST"]
)
def api_shorts():

    try:

        if request.method == "POST":

            body = (
                request.get_json(
                    silent=True
                )
                or {}
            )

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

        options = build_search_options()

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

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

        for entry in (
            entries or []
        ):

            item = build_search_item(
                entry
            )

            if not item:
                continue

            results.append(
                item
            )

            if len(results) >= limit:

                break

        return jsonify({

            "success":
                True,

            "query":
                query,

            "count":
                len(results),

            "results":
                results,

            "continuation":
                None,

            "has_more":
                False,

            "requested_limit":
                limit,

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# OLD COMPATIBILITY SEARCH
# ============================================================

@app.route(
    "/search",
    methods=["GET", "POST"]
)
def old_search():

    try:

        if request.method == "POST":

            body = (
                request.get_json(
                    silent=True
                )
                or {}
            )

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
                "error":
                    "Search query is required"
            }), 400

        limit = max(
            1,
            min(
                limit,
                MAX_SEARCH_LIMIT
            )
        )

        options = build_search_options()

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

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

        for entry in (
            entries or []
        ):

            item = build_search_item(
                entry
            )

            if item:

                results.append(
                    item
                )

        return jsonify({

            "success":
                True,

            "query":
                query,

            "count":
                len(results),

            "results":
                results,

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# OLD DOWNLOAD-LINKS COMPATIBILITY
# ============================================================

@app.route(
    "/get-download-links",
    methods=["GET", "POST"]
)
def old_download_links():

    return api_download_links()


# ============================================================
# LEGACY LOCAL HOME CONTENT
# ============================================================

HOME_CONTENT_FILE = (
    Path(__file__).resolve().parent
    / "home_content.json"
)


def legacy_home_content():

    if not HOME_CONTENT_FILE.exists():

        return {
            "app": "MAYOTUBE",
            "version": 1,
            "enabled": False,
            "items": []
        }

    try:

        with open(
            HOME_CONTENT_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            content = json.load(
                file
            )

        if isinstance(
            content,
            dict
        ):

            return content

    except Exception:
        pass

    return {
        "app": "MAYOTUBE",
        "version": 1,
        "enabled": False,
        "items": []
    }


# ============================================================
# CMS DEFAULT CONTENT
# ============================================================

def default_cms_content():

    return {

        "app":
            "MAYOTUBE",

        "version":
            1,

        "enabled":
            True,

        "updated_at":
            utc_now(),

        "settings": {

            "home_content_enabled":
                True

        },

        "items":
            []

    }


# ============================================================
# BLOB HELPERS
# ============================================================

def blob_is_configured():

    return bool(
        BlobClient
        and BLOB_TOKEN
    )


def blob_client():

    if not BlobClient:

        raise Exception(
            "Vercel Blob SDK is not available"
        )

    if not BLOB_TOKEN:

        raise Exception(
            "BLOB_READ_WRITE_TOKEN is not configured"
        )

    return BlobClient(
        token=BLOB_TOKEN
    )


def blob_result_value(
    result,
    key,
    default=None
):

    if result is None:
        return default

    if isinstance(
        result,
        dict
    ):

        return result.get(
            key,
            default
        )

    attr_map = {
        "url": "url",
        "downloadUrl": "download_url",
        "pathname": "pathname",
        "contentType": "content_type",
        "etag": "etag"
    }

    attribute = attr_map.get(
        key,
        key
    )

    return getattr(
        result,
        attribute,
        default
    )


def load_blob_json():

    if not blob_is_configured():

        return None

    client = blob_client()

    try:

        result = client.get(
            CMS_CONTENT_PATH,
            access="public"
        )

        if result is None:

            return None

        body = getattr(
            result,
            "body",
            None
        )

        if body is not None:

            if isinstance(
                body,
                bytes
            ):

                return json.loads(
                    body.decode(
                        "utf-8"
                    )
                )

            return json.loads(
                body
            )

        stream = getattr(
            result,
            "stream",
            None
        )

        if stream is not None:

            chunks = []

            for chunk in stream:

                chunks.append(
                    chunk
                )

            raw = b"".join(
                chunks
            )

            return json.loads(
                raw.decode(
                    "utf-8"
                )
            )

    except Exception as error:

        message = clean_text(
            error
        ).lower()

        if (
            "not found"
            in message
            or "404"
            in message
        ):

            return None

        raise

    return None


def save_blob_json(
    content
):

    if not blob_is_configured():

        raise Exception(
            "Vercel Blob is not configured. "
            "Create/connect a Blob store and "
            "set BLOB_READ_WRITE_TOKEN."
        )

    raw = json.dumps(
        content,
        ensure_ascii=False,
        indent=2
    ).encode(
        "utf-8"
    )

    client = blob_client()

    result = client.put(
        CMS_CONTENT_PATH,
        raw,
        access="public",
        content_type="application/json",
        add_random_suffix=False,
        overwrite=True
    )

    return {
        "pathname":
            blob_result_value(
                result,
                "pathname",
                CMS_CONTENT_PATH
            ),
        "url":
            blob_result_value(
                result,
                "url",
                ""
            ),
        "etag":
            blob_result_value(
                result,
                "etag",
                ""
            )
    }


# ============================================================
# CMS CONTENT LOAD / SAVE
# ============================================================

def load_cms_content():

    if blob_is_configured():

        try:

            content = load_blob_json()

            if isinstance(
                content,
                dict
            ):

                return content

        except Exception:
            pass

    return legacy_home_content()


def save_cms_content(
    content
):

    content = dict(
        content
    )

    content[
        "app"
    ] = "MAYOTUBE"

    content[
        "updated_at"
    ] = utc_now()

    if not isinstance(
        content.get("items"),
        list
    ):

        content[
            "items"
        ] = []

    return save_blob_json(
        content
    )


# ============================================================
# HOME ITEM PREPARATION
# ============================================================

def prepare_home_items(
    content
):

    if not content.get(
        "enabled",
        True
    ):

        return []

    items = content.get(
        "items",
        []
    )

    if not isinstance(
        items,
        list
    ):

        return []

    valid_items = []

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        if not item.get(
            "enabled",
            False
        ):
            continue

        item_id = str(
            item.get(
                "id",
                ""
            )
        ).strip()

        item_type = str(
            item.get(
                "type",
                ""
            )
        ).strip().lower()

        if not item_id:
            continue

        if not item_type:
            continue

        prepared_item = dict(
            item
        )

        prepared_item[
            "id"
        ] = item_id

        prepared_item[
            "type"
        ] = item_type

        prepared_item[
            "order"
        ] = safe_int(
            item.get(
                "order",
                0
            ),
            0
        )

        valid_items.append(
            prepared_item
        )

    valid_items.sort(
        key=lambda item: (
            item.get(
                "order",
                0
            ),
            item.get(
                "id",
                ""
            )
        )
    )

    return valid_items


# ============================================================
# API: REMOTE HOME CONTENT
# ============================================================

@app.route(
    "/api/home-content",
    methods=["GET"]
)
def api_home_content():

    try:

        content = load_cms_content()

        items = prepare_home_items(
            content
        )

        return jsonify({

            "success":
                True,

            "app":
                content.get(
                    "app",
                    "MAYOTUBE"
                ),

            "version":
                content.get(
                    "version",
                    1
                ),

            "updated_at":
                content.get(
                    "updated_at",
                    ""
                ),

            "enabled":
                content.get(
                    "enabled",
                    True
                ),

            "settings":
                content.get(
                    "settings",
                    {}
                ),

            "count":
                len(items),

            "items":
                items

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                ),

            "items":
                []

        }), 500


# ============================================================
# API: HOME CONTENT HEALTH
# ============================================================

@app.route(
    "/api/home-content/health",
    methods=["GET"]
)
def home_content_health():

    return jsonify({

        "success":
            True,

        "app":
            "MAYOTUBE",

        "service":
            "home-content",

        "content_file":
            "Vercel Blob CMS"
            if blob_is_configured()
            else "home_content.json",

        "blob_configured":
            blob_is_configured(),

        "legacy_file_exists":
            HOME_CONTENT_FILE.exists(),

        "content_path":
            CMS_CONTENT_PATH,

    })


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def get_admin_token():

    authorization = clean_text(
        request.headers.get(
            "Authorization"
        )
    )

    if authorization.lower().startswith(
        "bearer "
    ):

        return clean_text(
            authorization[7:]
        )

    token = clean_text(
        request.headers.get(
            "X-MAYOTUBE-ADMIN-TOKEN"
        )
    )

    if token:

        return token

    if request.method in [
        "POST",
        "PUT",
        "PATCH",
        "DELETE"
    ]:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        return clean_text(
            body.get(
                "admin_token"
            )
        )

    return ""


def admin_is_configured():

    return bool(
        ADMIN_TOKEN
    )


def require_admin():

    if not ADMIN_TOKEN:

        return jsonify({

            "success":
                False,

            "error":
                "Admin CMS is not configured. "
                "Set MAYOTUBE_ADMIN_TOKEN in Vercel "
                "Environment Variables."

        }), 503

    supplied = get_admin_token()

    if (
        not supplied
        or supplied != ADMIN_TOKEN
    ):

        return jsonify({

            "success":
                False,

            "error":
                "Unauthorized"

        }), 401

    return None


# ============================================================
# CMS ITEM NORMALIZATION
# ============================================================

ALLOWED_CMS_TYPES = [
    "message",
    "announcement",
    "notification",
    "image",
    "video",
    "youtube",
    "audio",
    "button",
    "link",
    "donation",
    "advertisement",
    "website",
    "channel"
]


def normalize_cms_item(
    payload,
    existing=None
):

    payload = (
        payload
        if isinstance(
            payload,
            dict
        )
        else {}
    )

    existing = (
        existing
        if isinstance(
            existing,
            dict
        )
        else {}
    )

    item = dict(
        existing
    )

    item_id = clean_text(
        payload.get(
            "id"
        )
        or existing.get(
            "id"
        )
    )

    if not item_id:

        item_id = generate_id(
            "content"
        )

    item_type = clean_text(
        payload.get(
            "type"
        )
        or existing.get(
            "type"
        )
        or "message"
    ).lower()

    if item_type not in ALLOWED_CMS_TYPES:

        raise ValueError(
            "Invalid content type. "
            "Allowed types: "
            + ", ".join(
                ALLOWED_CMS_TYPES
            )
        )

    title = clean_text(
        payload.get(
            "title",
            existing.get(
                "title",
                ""
            )
        )
    )

    message = clean_text(
        payload.get(
            "message",
            existing.get(
                "message",
                ""
            )
        )
    )

    description = clean_text(
        payload.get(
            "description",
            existing.get(
                "description",
                ""
            )
        )
    )

    image_url = clean_text(
        payload.get(
            "image_url",
            existing.get(
                "image_url",
                ""
            )
        )
    )

    video_url = clean_text(
        payload.get(
            "video_url",
            existing.get(
                "video_url",
                ""
            )
        )
    )

    link_url = clean_text(
        payload.get(
            "link_url",
            existing.get(
                "link_url",
                ""
            )
        )
    )

    button_text = clean_text(
        payload.get(
            "button_text",
            existing.get(
                "button_text",
                ""
            )
        )
    )

    order = safe_int(
        payload.get(
            "order",
            existing.get(
                "order",
                0
            )
        ),
        0
    )

    enabled_value = payload.get(
        "enabled",
        existing.get(
            "enabled",
            True
        )
    )

    if isinstance(
        enabled_value,
        str
    ):

        enabled_value = (
            enabled_value.lower()
            not in [
                "false",
                "0",
                "no",
                "off"
            ]
        )

    else:

        enabled_value = bool(
            enabled_value
        )

    item.update({

        "id":
            item_id,

        "type":
            item_type,

        "title":
            title,

        "message":
            message,

        "description":
            description,

        "image_url":
            image_url,

        "video_url":
            video_url,

        "link_url":
            link_url,

        "button_text":
            button_text,

        "enabled":
            enabled_value,

        "order":
            order,

        "updated_at":
            utc_now(),

    })

    if not item.get(
        "created_at"
    ):

        item[
            "created_at"
        ] = utc_now()

    if (
        "metadata"
        in payload
        and isinstance(
            payload["metadata"],
            dict
        )
    ):

        item[
            "metadata"
        ] = payload[
            "metadata"
        ]

    elif "metadata" not in item:

        item[
            "metadata"
        ] = {}

    return item


# ============================================================
# ADMIN: CMS STATUS
# ============================================================

@app.route(
    "/api/admin/status",
    methods=["GET"]
)
def admin_status():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    return jsonify({

        "success":
            True,

        "service":
            "MAYOTUBE CMS",

        "cms_version":
            "1.0",

        "admin_configured":
            admin_is_configured(),

        "blob_sdk":
            bool(
                BlobClient
            ),

        "blob_configured":
            blob_is_configured(),

        "content_path":
            CMS_CONTENT_PATH,

        "media_prefix":
            CMS_MEDIA_PREFIX,

        "allowed_types":
            ALLOWED_CMS_TYPES,

    })


# ============================================================
# ADMIN: GET ALL CONTENT
# ============================================================

@app.route(
    "/api/admin/content",
    methods=["GET"]
)
def admin_get_content():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        content = load_cms_content()

        items = content.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            items = []

        items = [
            item
            for item in items
            if isinstance(
                item,
                dict
            )
        ]

        items.sort(
            key=lambda item: (
                safe_int(
                    item.get(
                        "order",
                        0
                    ),
                    0
                ),
                clean_text(
                    item.get(
                        "id"
                    )
                )
            )
        )

        return jsonify({

            "success":
                True,

            "app":
                content.get(
                    "app",
                    "MAYOTUBE"
                ),

            "version":
                content.get(
                    "version",
                    1
                ),

            "enabled":
                content.get(
                    "enabled",
                    True
                ),

            "updated_at":
                content.get(
                    "updated_at",
                    ""
                ),

            "settings":
                content.get(
                    "settings",
                    {}
                ),

            "count":
                len(items),

            "items":
                items

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: CREATE CONTENT
# ============================================================

@app.route(
    "/api/admin/content",
    methods=["POST"]
)
def admin_create_content():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        content = load_cms_content()

        items = content.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            items = []

        item = normalize_cms_item(
            body
        )

        items.append(
            item
        )

        content[
            "items"
        ] = items

        content[
            "version"
        ] = safe_int(
            content.get(
                "version",
                1
            ),
            1
        ) + 1

        storage = save_cms_content(
            content
        )

        return jsonify({

            "success":
                True,

            "message":
                "Content created",

            "item":
                item,

            "storage":
                storage

        }), 201

    except ValueError as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 400

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: UPDATE CONTENT
# ============================================================

@app.route(
    "/api/admin/content/<item_id>",
    methods=["PUT"]
)
def admin_update_content(
    item_id
):

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        item_id = clean_text(
            item_id
        )

        if not item_id:

            return jsonify({

                "success":
                    False,

                "error":
                    "Content ID is required"

            }), 400

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        content = load_cms_content()

        items = content.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            items = []

        found = False
        updated_item = None

        for index, existing in enumerate(
            items
        ):

            if not isinstance(
                existing,
                dict
            ):
                continue

            if clean_text(
                existing.get(
                    "id"
                )
            ) != item_id:

                continue

            updated_item = normalize_cms_item(
                body,
                existing
            )

            items[
                index
            ] = updated_item

            found = True

            break

        if not found:

            return jsonify({

                "success":
                    False,

                "error":
                    "Content not found"

            }), 404

        content[
            "items"
        ] = items

        content[
            "version"
        ] = safe_int(
            content.get(
                "version",
                1
            ),
            1
        ) + 1

        storage = save_cms_content(
            content
        )

        return jsonify({

            "success":
                True,

            "message":
                "Content updated",

            "item":
                updated_item,

            "storage":
                storage

        })

    except ValueError as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 400

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: DELETE CONTENT
# ============================================================

@app.route(
    "/api/admin/content/<item_id>",
    methods=["DELETE"]
)
def admin_delete_content(
    item_id
):

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        item_id = clean_text(
            item_id
        )

        content = load_cms_content()

        items = content.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            items = []

        old_count = len(
            items
        )

        deleted_item = None
        remaining = []

        for item in items:

            if (
                isinstance(
                    item,
                    dict
                )
                and clean_text(
                    item.get(
                        "id"
                    )
                ) == item_id
            ):

                deleted_item = item

                continue

            remaining.append(
                item
            )

        if deleted_item is None:

            return jsonify({

                "success":
                    False,

                "error":
                    "Content not found"

            }), 404

        content[
            "items"
        ] = remaining

        content[
            "version"
        ] = safe_int(
            content.get(
                "version",
                1
            ),
            1
        ) + 1

        storage = save_cms_content(
            content
        )

        return jsonify({

            "success":
                True,

            "message":
                "Content deleted",

            "deleted":
                deleted_item,

            "remaining":
                len(
                    remaining
                ),

            "previous_count":
                old_count,

            "storage":
                storage

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: ENABLE / DISABLE CONTENT
# ============================================================

@app.route(
    "/api/admin/content/<item_id>/toggle",
    methods=["PATCH"]
)
def admin_toggle_content(
    item_id
):

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        item_id = clean_text(
            item_id
        )

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        content = load_cms_content()

        items = content.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            items = []

        for item in items:

            if not isinstance(
                item,
                dict
            ):
                continue

            if clean_text(
                item.get(
                    "id"
                )
            ) != item_id:

                continue

            if "enabled" in body:

                value = body.get(
                    "enabled"
                )

                if isinstance(
                    value,
                    str
                ):

                    value = (
                        value.lower()
                        not in [
                            "false",
                            "0",
                            "no",
                            "off"
                        ]
                    )

                item[
                    "enabled"
                ] = bool(
                    value
                )

            else:

                item[
                    "enabled"
                ] = not bool(
                    item.get(
                        "enabled",
                        False
                    )
                )

            item[
                "updated_at"
            ] = utc_now()

            content[
                "version"
            ] = safe_int(
                content.get(
                    "version",
                    1
                ),
                1
            ) + 1

            storage = save_cms_content(
                content
            )

            return jsonify({

                "success":
                    True,

                "message":
                    "Content status changed",

                "item":
                    item,

                "storage":
                    storage

            })

        return jsonify({

            "success":
                False,

            "error":
                "Content not found"

        }), 404

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: HOME CMS ENABLE / DISABLE
# ============================================================

@app.route(
    "/api/admin/home/toggle",
    methods=["PATCH"]
)
def admin_toggle_home():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        content = load_cms_content()

        if "enabled" in body:

            value = body.get(
                "enabled"
            )

            if isinstance(
                value,
                str
            ):

                value = (
                    value.lower()
                    not in [
                        "false",
                        "0",
                        "no",
                        "off"
                    ]
                )

            content[
                "enabled"
            ] = bool(
                value
            )

        else:

            content[
                "enabled"
            ] = not bool(
                content.get(
                    "enabled",
                    True
                )
            )

        content[
            "version"
        ] = safe_int(
            content.get(
                "version",
                1
            ),
            1
        ) + 1

        storage = save_cms_content(
            content
        )

        return jsonify({

            "success":
                True,

            "message":
                "Home CMS status changed",

            "enabled":
                content[
                    "enabled"
                ],

            "storage":
                storage

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: MEDIA UPLOAD
# ============================================================

def allowed_media_type(
    content_type,
    filename
):

    content_type = clean_text(
        content_type
    ).lower()

    filename = clean_text(
        filename
    ).lower()

    image_extensions = [
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    ]

    video_extensions = [
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".mkv"
    ]

    audio_extensions = [
        ".mp3",
        ".m4a",
        ".aac",
        ".wav",
        ".ogg"
    ]

    if content_type.startswith(
        "image/"
    ):

        return True

    if content_type.startswith(
        "video/"
    ):

        return True

    if content_type.startswith(
        "audio/"
    ):

        return True

    return (
        any(
            filename.endswith(
                ext
            )
            for ext in (
                image_extensions
                + video_extensions
                + audio_extensions
            )
        )
    )


@app.route(
    "/api/admin/media",
    methods=["POST"]
)
def admin_upload_media():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        if not blob_is_configured():

            return jsonify({

                "success":
                    False,

                "error":
                    "Vercel Blob is not configured. "
                    "Set BLOB_READ_WRITE_TOKEN."

            }), 503

        uploaded_file = (
            request.files.get(
                "file"
            )
        )

        if uploaded_file is None:

            return jsonify({

                "success":
                    False,

                "error":
                    "No file was uploaded. "
                    "Use multipart/form-data field: file"

            }), 400

        original_name = clean_text(
            uploaded_file.filename
        )

        if not original_name:

            return jsonify({

                "success":
                    False,

                "error":
                    "Filename is required"

            }), 400

        content_type = clean_text(
            uploaded_file.mimetype
        ).lower()

        if not allowed_media_type(
            content_type,
            original_name
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Unsupported media type"

            }), 400

        extension = (
            Path(
                original_name
            ).suffix.lower()
        )

        safe_extension = re.sub(
            r"[^a-z0-9.]",
            "",
            extension
        )

        if not safe_extension:

            safe_extension = ".bin"

        media_id = uuid.uuid4().hex

        pathname = (
            CMS_MEDIA_PREFIX
            + "/"
            + media_id
            + safe_extension
        )

        file_bytes = (
            uploaded_file.read()
        )

        if not file_bytes:

            return jsonify({

                "success":
                    False,

                "error":
                    "Uploaded file is empty"

            }), 400

        client = blob_client()

        is_large_media = (
            len(file_bytes)
            >= 5 * 1024 * 1024
        )

        result = client.put(
            pathname,
            file_bytes,
            access="public",
            content_type=(
                content_type
                or "application/octet-stream"
            ),
            add_random_suffix=False,
            overwrite=False,
            multipart=is_large_media
        )

        blob_url = blob_result_value(
            result,
            "url",
            ""
        )

        download_url = blob_result_value(
            result,
            "downloadUrl",
            ""
        )

        return jsonify({

            "success":
                True,

            "message":
                "Media uploaded",

            "media":
                {

                    "id":
                        media_id,

                    "filename":
                        original_name,

                    "content_type":
                        content_type,

                    "size":
                        len(
                            file_bytes
                        ),

                    "pathname":
                        blob_result_value(
                            result,
                            "pathname",
                            pathname
                        ),

                    "url":
                        blob_url,

                    "download_url":
                        download_url,

                    "etag":
                        blob_result_value(
                            result,
                            "etag",
                            ""
                        )

                }

        }), 201

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: MEDIA LIST
# ============================================================

@app.route(
    "/api/admin/media",
    methods=["GET"]
)
def admin_list_media():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        if not blob_is_configured():

            return jsonify({

                "success":
                    False,

                "error":
                    "Vercel Blob is not configured"

            }), 503

        client = blob_client()

        listing = client.list_objects(
            prefix=CMS_MEDIA_PREFIX + "/"
        )

        blobs = (
            getattr(
                listing,
                "blobs",
                None
            )
            if listing is not None
            else None
        )

        if blobs is None and isinstance(
            listing,
            dict
        ):

            blobs = listing.get(
                "blobs",
                []
            )

        if blobs is None:

            blobs = []

        media = []

        for blob in blobs:

            media.append({

                "pathname":
                    blob_result_value(
                        blob,
                        "pathname",
                        ""
                    ),

                "url":
                    blob_result_value(
                        blob,
                        "url",
                        ""
                    ),

                "download_url":
                    blob_result_value(
                        blob,
                        "downloadUrl",
                        ""
                    ),

                "content_type":
                    blob_result_value(
                        blob,
                        "contentType",
                        ""
                    ),

                "size":
                    safe_int(
                        blob_result_value(
                            blob,
                            "size",
                            0
                        ),
                        0
                    ),

                "etag":
                    blob_result_value(
                        blob,
                        "etag",
                        ""
                    ),

            })

        return jsonify({

            "success":
                True,

            "count":
                len(media),

            "media":
                media

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: MEDIA DELETE
# ============================================================

@app.route(
    "/api/admin/media",
    methods=["DELETE"]
)
def admin_delete_media():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        if not blob_is_configured():

            return jsonify({

                "success":
                    False,

                "error":
                    "Vercel Blob is not configured"

            }), 503

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        blob_url = clean_text(
            body.get(
                "url"
            )
        )

        pathname = clean_text(
            body.get(
                "pathname"
            )
        )

        target = (
            blob_url
            or pathname
        )

        if not target:

            return jsonify({

                "success":
                    False,

                "error":
                    "Blob URL or pathname is required"

            }), 400

        if (
            pathname
            and not pathname.startswith(
                CMS_MEDIA_PREFIX + "/"
            )
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid media pathname"

            }), 400

        client = blob_client()

        client.delete(
            target
        )

        return jsonify({

            "success":
                True,

            "message":
                "Media deleted",

            "target":
                target

        })

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# ADMIN: CMS CONTENT INITIALIZATION
# ============================================================

@app.route(
    "/api/admin/content/initialize",
    methods=["POST"]
)
def admin_initialize_content():

    auth_error = require_admin()

    if auth_error:
        return auth_error

    try:

        if not blob_is_configured():

            return jsonify({

                "success":
                    False,

                "error":
                    "Vercel Blob is not configured"

            }), 503

        existing = load_blob_json()

        if isinstance(
            existing,
            dict
        ):

            return jsonify({

                "success":
                    True,

                "message":
                    "CMS content already exists",

                "created":
                    False,

                "content":
                    existing

            })

        content = default_cms_content()

        legacy = legacy_home_content()

        if isinstance(
            legacy,
            dict
        ):

            legacy_items = legacy.get(
                "items",
                []
            )

            if isinstance(
                legacy_items,
                list
            ):

                content[
                    "items"
                ] = legacy_items

            content[
                "settings"
            ] = legacy.get(
                "settings",
                {}
            )

            content[
                "enabled"
            ] = legacy.get(
                "enabled",
                True
            )

        content[
            "version"
        ] = 1

        storage = save_cms_content(
            content
        )

        return jsonify({

            "success":
                True,

            "message":
                "CMS content initialized",

            "created":
                True,

            "content":
                content,

            "storage":
                storage

        }), 201

    except Exception as error:

        return jsonify({

            "success":
                False,

            "error":
                clean_text(
                    error
                )

        }), 500


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    provider_status = (
        get_provider_status()
    )

    return jsonify({

        "success":
            True,

        "status":
            "running",

        "service":
            APP_NAME,

        "version":
            APP_VERSION,

        "backend":
            "Vercel",

        "youtube_extractor":
            "yt-dlp",

        "search_limit":
            MAX_SEARCH_LIMIT,

        "cookies_configured":
            bool(
                os.environ.get(
                    "YOUTUBE_COOKIES_B64",
                    ""
                ).strip()
            ),

        "po_token_configured":
            bool(
                get_po_token()
            ),

        "po_token_provider":
            provider_status,

        "youtube_client_strategy":
            (
                "bgutil-mweb-first"
                if is_bgutil_configured()
                else "fallback-clients"
            ),

        "home_content":
            HOME_CONTENT_FILE.exists(),

        "cms":
            {

                "version":
                    "1.0",

                "admin_configured":
                    admin_is_configured(),

                "blob_sdk":
                    bool(
                        BlobClient
                    ),

                "blob_configured":
                    blob_is_configured(),

                "content_path":
                    CMS_CONTENT_PATH,

            }

    })


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({

        "success":
            True,

        "name":
            APP_NAME,

        "version":
            APP_VERSION,

        "status":
            "running",

        "backend":
            "Vercel",

        "features": [

            "youtube-video-info",

            "youtube-download-links",

            "youtube-search",

            "youtube-shorts",

            "multiple-youtube-clients",

            "automatic-po-token-provider",

            "bgutil-http-provider",

            "mweb-provider-mode",

            "optional-youtube-cookies",

            "optional-manual-youtube-po-token",

            "50-results-per-request",

            "future-ready-provider-architecture",

            "remote-home-content",

            "remote-home-messages",

            "remote-home-images",

            "remote-home-videos",

            "remote-home-audio",

            "remote-home-youtube-links",

            "remote-home-channel-links",

            "remote-home-website-links",

            "remote-home-donations",

            "remote-home-advertisements",

            "remote-home-buttons",

            "admin-cms",

            "cms-create-content",

            "cms-edit-content",

            "cms-delete-content",

            "cms-enable-disable",

            "cms-media-upload",

            "cms-media-list",

            "cms-media-delete",

            "vercel-blob-storage",

        ],

        "endpoints": {

            "health":
                "/health",

            "home_content":
                "/api/home-content",

            "home_content_health":
                "/api/home-content/health",

            "video_info":
                "/api/video-info",

            "download_links":
                "/api/download-links",

            "download":
                "/api/download",

            "search":
                "/api/search",

            "shorts":
                "/api/shorts",

            "old_search":
                "/search",

            "old_download_links":
                "/get-download-links",

            "admin_status":
                "/api/admin/status",

            "admin_content":
                "/api/admin/content",

            "admin_content_initialize":
                "/api/admin/content/initialize",

            "admin_home_toggle":
                "/api/admin/home/toggle",

            "admin_media":
                "/api/admin/media",

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
