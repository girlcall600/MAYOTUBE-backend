from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
import re
import os

app = Flask(__name__)
CORS(app)

APP_NAME = "MAYOTUBE API"
VERSION = "3.0"


# =========================================================
# COMMON HELPERS
# =========================================================

def clean_error(error):
    text = str(error)

    text = re.sub(
        r"\x1b\[[0-9;]*m",
        "",
        text
    )

    return text[:1500]


def is_valid_url(url):
    if not url:
        return False

    return (
        url.startswith("http://")
        or url.startswith("https://")
    )


def get_ydl_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Mobile Safari/537.36"
            )
        }
    }


def format_duration(seconds):
    if not seconds:
        return "0:00"

    try:
        seconds = int(seconds)
    except Exception:
        return "0:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def platform_name(info):
    extractor = str(
        info.get("extractor_key", "")
    ).lower()

    webpage = str(
        info.get("webpage_url", "")
    ).lower()

    if "youtube" in extractor or "youtube" in webpage:
        return "YouTube"

    if "tiktok" in extractor or "tiktok" in webpage:
        return "TikTok"

    if "facebook" in extractor or "facebook" in webpage:
        return "Facebook"

    return extractor or "Unknown"


def make_filename(title, ext):
    title = title or "MAYOTUBE_VIDEO"

    title = re.sub(
        r'[\\/:*?"<>|]+',
        "",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    if not title:
        title = "MAYOTUBE_VIDEO"

    if not ext:
        ext = "mp4"

    return f"{title}.{ext}"


# =========================================================
# VIDEO INFORMATION
# =========================================================

def simplify_info(info):
    return {
        "id": info.get("id"),

        "title": (
            info.get("title")
            or "Untitled"
        ),

        "description": (
            info.get("description")
            or ""
        ),

        "thumbnail": info.get(
            "thumbnail"
        ),

        "duration": (
            info.get("duration")
            or 0
        ),

        "duration_text": format_duration(
            info.get("duration")
        ),

        "uploader": (
            info.get("uploader")
            or info.get("channel")
        ),

        "channel": info.get(
            "channel"
        ),

        "channel_id": info.get(
            "channel_id"
        ),

        "view_count": info.get(
            "view_count"
        ),

        "like_count": info.get(
            "like_count"
        ),

        "comment_count": info.get(
            "comment_count"
        ),

        "upload_date": info.get(
            "upload_date"
        ),

        "webpage_url": info.get(
            "webpage_url"
        ),

        "platform": platform_name(
            info
        ),

        "width": info.get(
            "width"
        ),

        "height": info.get(
            "height"
        ),

        "fps": info.get(
            "fps"
        ),

        "is_live": info.get(
            "is_live",
            False
        ),

        "live_status": info.get(
            "live_status"
        )
    }


# =========================================================
# FORMAT INFORMATION
# =========================================================

def get_formats(info):
    formats = []

    for item in info.get(
        "formats",
        []
    ):

        url = item.get("url")

        if not url:
            continue

        height = item.get(
            "height"
        )

        width = item.get(
            "width"
        )

        filesize = (
            item.get("filesize")
            or item.get("filesize_approx")
        )

        ext = item.get(
            "ext"
        )

        format_id = item.get(
            "format_id"
        )

        vcodec = item.get(
            "vcodec"
        )

        acodec = item.get(
            "acodec"
        )

        if (
            vcodec == "none"
            and acodec != "none"
        ):
            kind = "audio"

        elif (
            vcodec != "none"
            and acodec != "none"
        ):
            kind = "video+audio"

        elif vcodec != "none":
            kind = "video"

        else:
            kind = "unknown"

        if kind == "audio":
            quality = "MP3"

        elif height:
            quality = f"{height}p"

        elif item.get("resolution"):
            quality = item.get(
                "resolution"
            )

        else:
            quality = "Unknown"

        formats.append({
            "format_id": format_id,
            "url": url,
            "ext": ext,
            "height": height,
            "width": width,
            "fps": item.get("fps"),
            "filesize": filesize,
            "vcodec": vcodec,
            "acodec": acodec,
            "kind": kind,
            "quality": quality,
            "format_note": item.get(
                "format_note"
            ),
            "resolution": item.get(
                "resolution"
            ),
            "tbr": item.get(
                "tbr"
            )
        })

    return formats


# =========================================================
# BEST VIDEO QUALITIES
# =========================================================

def get_best_quality_formats(info):

    all_formats = get_formats(
        info
    )

    selected = {}

    for item in all_formats:

        if item["kind"] not in (
            "video",
            "video+audio"
        ):
            continue

        height = item.get(
            "height"
        )

        if not height:
            continue

        quality = f"{height}p"

        if quality not in selected:

            selected[quality] = item

        else:

            current = selected[
                quality
            ]

            if (
                item["kind"]
                == "video+audio"
                and current["kind"]
                != "video+audio"
            ):

                selected[quality] = item

            elif (
                item["kind"]
                == current["kind"]
            ):

                new_size = (
                    item.get(
                        "filesize"
                    )
                    or 0
                )

                old_size = (
                    current.get(
                        "filesize"
                    )
                    or 0
                )

                if new_size > old_size:
                    selected[quality] = item

    result = list(
        selected.values()
    )

    result.sort(
        key=lambda x:
            x.get("height") or 0,
        reverse=True
    )

    return result


# =========================================================
# AUDIO FORMATS
# =========================================================

def get_audio_formats(info):

    all_formats = get_formats(
        info
    )

    audio = [
        item
        for item in all_formats
        if item["kind"] == "audio"
    ]

    audio.sort(
        key=lambda x:
            x.get("tbr") or 0,
        reverse=True
    )

    return audio


# =========================================================
# FIND SELECTED FORMAT
# =========================================================

def find_selected_format(
    info,
    quality=None,
    format_id=None
):

    all_formats = get_formats(
        info
    )

    if format_id:

        for item in all_formats:

            if str(
                item.get("format_id")
            ) == str(format_id):

                return item

    if quality:

        requested_quality = (
            str(quality)
            .lower()
            .replace(" ", "")
        )

        if requested_quality in (
            "mp3",
            "audio",
            "audioonly",
            "m4a"
        ):

            audio = get_audio_formats(
                info
            )

            if audio:
                return audio[0]

        match = re.search(
            r"(\d+)",
            requested_quality
        )

        if match:

            requested_height = int(
                match.group(1)
            )

            candidates = [
                item
                for item in all_formats
                if item.get("height")
                == requested_height
                and item["kind"] in (
                    "video",
                    "video+audio"
                )
            ]

            if candidates:

                candidates.sort(
                    key=lambda x: (
                        1
                        if x["kind"]
                        == "video+audio"
                        else 0,

                        x.get(
                            "filesize"
                        )
                        or 0
                    ),
                    reverse=True
                )

                return candidates[0]

    return None


# =========================================================
# HOME
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({

        "status": "running",

        "name": APP_NAME,

        "version": VERSION,

        "message":
            "MAYOTUBE backend is active",

        "platforms": [
            "YouTube",
            "TikTok",
            "Facebook"
        ],

        "features": [
            "search",
            "video-info",
            "quality-selector",
            "direct-download-url",
            "audio",
            "mp3",
            "thumbnail",
            "duration",
            "views",
            "channel"
        ],

        "endpoints": [
            "/",
            "/health",
            "/api/search",
            "/api/video-info",
            "/api/download-links",
            "/api/download"
        ]
    })


# =========================================================
# HEALTH
# =========================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status": "ok",

        "service": APP_NAME,

        "version": VERSION
    })


# =========================================================
# VIDEO INFO
# =========================================================

@app.route(
    "/api/video-info",
    methods=["GET", "POST"]
)
def video_info():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        url = (
            request.args.get("url")
            or data.get("url")
        )

        if not is_valid_url(url):

            return jsonify({

                "success": False,

                "error":
                    "Valid video URL is required"
            }), 400

        options = get_ydl_options()

        with YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        return jsonify({

            "success": True,

            "data":
                simplify_info(info)
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                clean_error(e)

        }), 500


# =========================================================
# DOWNLOAD LINKS
# =========================================================

@app.route(
    "/api/download-links",
    methods=["GET", "POST"]
)
def download_links():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        url = (
            request.args.get("url")
            or data.get("url")
        )

        if not is_valid_url(url):

            return jsonify({

                "success": False,

                "error":
                    "Valid video URL is required"
            }), 400

        options = get_ydl_options()

        with YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        quality_formats = (
            get_best_quality_formats(
                info
            )
        )

        audio_formats = (
            get_audio_formats(
                info
            )
        )

        return jsonify({

            "success": True,

            "data": {

                "video":
                    simplify_info(info),

                "qualities":
                    quality_formats,

                "audio":
                    audio_formats
            }
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                clean_error(e)

        }), 500


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/api/download",
    methods=["GET", "POST"]
)
def download():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        url = (
            request.args.get("url")
            or data.get("url")
        )

        quality = (
            request.args.get("quality")
            or data.get("quality")
        )

        format_id = (
            request.args.get("format_id")
            or data.get("format_id")
        )

        if not is_valid_url(url):

            return jsonify({

                "success": False,

                "error":
                    "Valid video URL is required"
            }), 400

        if not quality and not format_id:

            return jsonify({

                "success": False,

                "error":
                    "Quality or format_id is required"
            }), 400

        options = get_ydl_options()

        with YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        selected = find_selected_format(
            info,
            quality=quality,
            format_id=format_id
        )

        if not selected:

            return jsonify({

                "success": False,

                "error":
                    "Requested quality is not available"
            }), 404

        selected_url = selected.get(
            "url"
        )

        if not selected_url:

            return jsonify({

                "success": False,

                "error":
                    "Download URL is not available"
            }), 404

        ext = (
            selected.get("ext")
            or "mp4"
        )

        filename = make_filename(
            info.get("title"),
            ext
        )

        return jsonify({

            "success": True,

            "download": {

                "url":
                    selected_url,

                "quality":
                    selected.get(
                        "quality"
                    ),

                "format_id":
                    selected.get(
                        "format_id"
                    ),

                "ext":
                    ext,

                "kind":
                    selected.get(
                        "kind"
                    ),

                "filename":
                    filename,

                "title":
                    info.get(
                        "title"
                    ),

                "thumbnail":
                    info.get(
                        "thumbnail"
                    ),

                "platform":
                    platform_name(
                        info
                    )
            }
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                clean_error(e)

        }), 500


# =========================================================
# SEARCH
# =========================================================

@app.route(
    "/api/search",
    methods=["GET", "POST"]
)
def search():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        query = (
            request.args.get("q")
            or request.args.get(
                "query"
            )
            or data.get("q")
            or data.get("query")
        )

        if not query:

            return jsonify({

                "success": False,

                "error":
                    "Search query is required"
            }), 400

        limit = (
            request.args.get("limit")
            or data.get("limit")
            or 10
        )

        try:
            limit = int(limit)
        except Exception:
            limit = 10

        limit = max(
            1,
            min(limit, 20)
        )

        debug = (
            str(
                request.args.get(
                    "debug",
                    ""
                )
            ).lower()
            in (
                "1",
                "true",
                "yes"
            )
        )

        search_query = (
            f"ytsearch{limit}:{query}"
        )

        options = get_ydl_options()

        # Search diagnostic only:
        # use flat extraction for YouTube search.
        options["extract_flat"] = "in_playlist"

        with YoutubeDL(
            options
        ) as ydl:

            result = ydl.extract_info(
                search_query,
                download=False
            )

        entries = result.get(
            "entries",
            []
        )

        if entries is None:
            entries = []

        videos = []

        for item in entries:

            if not item:
                continue

            video_id = item.get(
                "id"
            )

            thumbnail = item.get(
                "thumbnail"
            )

            if (
                not thumbnail
                and video_id
            ):

                thumbnail = (
                    "https://i.ytimg.com/vi/"
                    + str(video_id)
                    + "/hqdefault.jpg"
                )

            webpage_url = item.get(
                "webpage_url"
            )

            if (
                not webpage_url
                and video_id
            ):

                webpage_url = (
                    "https://www.youtube.com/watch?v="
                    + str(video_id)
                )

            videos.append({

                "id":
                    video_id,

                "title":
                    item.get("title")
                    or "Untitled",

                "thumbnail":
                    thumbnail,

                "duration":
                    item.get(
                        "duration"
                    )
                    or 0,

                "duration_text":
                    format_duration(
                        item.get(
                            "duration"
                        )
                    ),

                "uploader":
                    item.get(
                        "uploader"
                    ),

                "channel":
                    item.get(
                        "channel"
                    ),

                "channel_id":
                    item.get(
                        "channel_id"
                    ),

                "view_count":
                    item.get(
                        "view_count"
                    ),

                "upload_date":
                    item.get(
                        "upload_date"
                    ),

                "url":
                    webpage_url,

                "webpage_url":
                    webpage_url,

                "platform":
                    "YouTube"
            })

        response = {

            "success": True,

            "query":
                query,

            "count":
                len(videos),

            "results":
                videos
        }

        # -----------------------------------------------------
        # TEMPORARY SEARCH DIAGNOSTIC
        # Only visible when ?debug=1 is supplied.
        # -----------------------------------------------------
        if debug:

            first_entry = (
                entries[0]
                if entries
                else None
            )

            response["diagnostic"] = {

                "result_type":
                    result.get("_type"),

                "extractor":
                    result.get(
                        "extractor"
                    ),

                "extractor_key":
                    result.get(
                        "extractor_key"
                    ),

                "webpage_url":
                    result.get(
                        "webpage_url"
                    ),

                "entry_count":
                    len(entries),

                "has_entries":
                    bool(entries),

                "result_keys":
                    list(result.keys())[:40],

                "first_entry_keys":
                    (
                        list(
                            first_entry.keys()
                        )[:40]
                        if isinstance(
                            first_entry,
                            dict
                        )
                        else []
                    )
            }

        return jsonify(
            response
        )

    except Exception as e:

        response = {

            "success": False,

            "error":
                clean_error(e)
        }

        if (
            str(
                request.args.get(
                    "debug",
                    ""
                )
            ).lower()
            in (
                "1",
                "true",
                "yes"
            )
        ):

            response["diagnostic"] = {

                "exception_type":
                    type(e).__name__,

                "error":
                    clean_error(e)
            }

        return jsonify(
            response
        ), 500


# =========================================================
# OLD API COMPATIBILITY
# =========================================================

@app.route(
    "/search",
    methods=["GET"]
)
def old_search():

    return search()


@app.route(
    "/get-download-links",
    methods=["POST"]
)
def old_download_links():

    return download_links()


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):

    return jsonify({

        "success": False,

        "error":
            "Endpoint not found"

    }), 404


@app.errorhandler(405)
def method_not_allowed(error):

    return jsonify({

        "success": False,

        "error":
            "Method not allowed"

    }), 405


@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "success": False,

        "error":
            "Internal server error"

    }), 500


# =========================================================
# LOCAL SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
