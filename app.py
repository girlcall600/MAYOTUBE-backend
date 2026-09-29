from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
import re
import os
import urllib.parse
import urllib.request
import json

app = Flask(__name__)
CORS(app)

APP_NAME = "MAYOTUBE API"
VERSION = "3.1"


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
# YOUTUBE INNERTUBE SEARCH
# =========================================================

def youtube_innertube_search(
    query,
    limit,
    continuation=None,
    shorts=False
):
    """
    YouTube InnerTube search.

    First request:
        query + search params

    Next requests:
        continuation token

    Returns:
        {
            "videos": [...],
            "continuation": "...",
            "has_more": True/False
        }
    """

    url = (
        "https://www.youtube.com/"
        "youtubei/v1/search"
        "?prettyPrint=false"
    )

    client_version = "2.20260114.08.00"

    context = {
        "client": {
            "clientName": "WEB",
            "clientVersion": client_version,
            "hl": "en",
            "gl": "US"
        }
    }

    if continuation:

        payload = {
            "context": context,
            "continuation": str(
                continuation
            )
        }

    else:

        # Normal YouTube video search.
        #
        # For Shorts we deliberately keep the query
        # separate. The Android side will request the
        # dedicated /api/shorts endpoint.
        search_query = str(query)

        if shorts:
            search_query = (
                search_query
                + " #shorts"
            )

        payload = {
            "context": context,
            "query": search_query,
            "params": "EgIQAQ=="
        }

    body = json.dumps(
        payload
    ).encode("utf-8")

    headers = {
        "Content-Type":
            "application/json",

        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0.0.0 "
            "Safari/537.36"
        ),

        "Accept":
            "application/json",

        "Origin":
            "https://www.youtube.com",

        "Referer":
            "https://www.youtube.com/",

        "X-YouTube-Client-Name":
            "1",

        "X-YouTube-Client-Version":
            client_version
    }

    request_object = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(
        request_object,
        timeout=20
    ) as response:

        raw = response.read()

    data = json.loads(
        raw.decode("utf-8")
    )

    videos = []
    continuation_token = None

    def find_continuation(value):

        nonlocal continuation_token

        if continuation_token:
            return

        if isinstance(
            value,
            dict
        ):

            # Common continuation structure.
            continuation_endpoint = value.get(
                "continuationEndpoint"
            )

            if isinstance(
                continuation_endpoint,
                dict
            ):

                continuation_command = (
                    continuation_endpoint.get(
                        "continuationCommand"
                    )
                )

                if isinstance(
                    continuation_command,
                    dict
                ):

                    token = (
                        continuation_command.get(
                            "token"
                        )
                    )

                    if token:
                        continuation_token = (
                            token
                        )
                        return

            # Another structure used by
            # some YouTube responses.
            reload_continuation = value.get(
                "reloadContinuationData"
            )

            if isinstance(
                reload_continuation,
                dict
            ):

                token = (
                    reload_continuation.get(
                        "continuation"
                    )
                )

                if token:
                    continuation_token = (
                        token
                    )
                    return

            append_continuation = value.get(
                "continuationItemRenderer"
            )

            if isinstance(
                append_continuation,
                dict
            ):

                endpoint = (
                    append_continuation.get(
                        "continuationEndpoint",
                        {}
                    )
                )

                command = (
                    endpoint.get(
                        "continuationCommand",
                        {}
                    )
                )

                token = command.get(
                    "token"
                )

                if token:
                    continuation_token = (
                        token
                    )
                    return

            for child in value.values():

                if continuation_token:
                    break

                find_continuation(
                    child
                )

        elif isinstance(
            value,
            list
        ):

            for child in value:

                if continuation_token:
                    break

                find_continuation(
                    child
                )

    def walk_videos(value):

        if len(videos) >= limit:
            return

        if isinstance(
            value,
            dict
        ):

            video_renderer = value.get(
                "videoRenderer"
            )

            if isinstance(
                video_renderer,
                dict
            ):

                video_id = (
                    video_renderer.get(
                        "videoId"
                    )
                )

                if video_id:

                    videos.append(
                        video_renderer
                    )

            for child in value.values():

                if len(videos) >= limit:
                    break

                walk_videos(
                    child
                )

        elif isinstance(
            value,
            list
        ):

            for child in value:

                if len(videos) >= limit:
                    break

                walk_videos(
                    child
                )

    walk_videos(
        data
    )

    find_continuation(
        data
    )

    return {
        "videos": videos,
        "continuation": continuation_token,
        "has_more": bool(
            continuation_token
        )
    }


def innertube_video_text(
    renderer,
    field
):
    value = renderer.get(
        field
    )

    if not isinstance(
        value,
        dict
    ):
        return None

    simple_text = value.get(
        "simpleText"
    )

    if simple_text:
        return simple_text

    runs = value.get(
        "runs"
    )

    if isinstance(
        runs,
        list
    ):

        parts = []

        for run in runs:

            if isinstance(
                run,
                dict
            ):

                text_value = run.get(
                    "text"
                )

                if text_value:
                    parts.append(
                        str(text_value)
                    )

        if parts:
            return "".join(parts)

    return None


def innertube_thumbnail(
    renderer
):

    thumbnails = (
        renderer.get(
            "thumbnail",
            {}
        )
        .get(
            "thumbnails",
            []
        )
    )

    if not thumbnails:
        return None

    best = thumbnails[-1]

    return best.get(
        "url"
    )


def parse_innertube_results(
    renderers
):

    videos = []

    for item in renderers:

        if not isinstance(
            item,
            dict
        ):
            continue

        video_id = item.get(
            "videoId"
        )

        if not video_id:
            continue

        title = (
            innertube_video_text(
                item,
                "title"
            )
            or "Untitled"
        )

        owner = (
            innertube_video_text(
                item,
                "ownerText"
            )
        )

        channel_id = None

        owner_runs = (
            item.get(
                "ownerText",
                {}
            ).get(
                "runs",
                []
            )
        )

        if owner_runs:

            first_owner = (
                owner_runs[0]
                if isinstance(
                    owner_runs[0],
                    dict
                )
                else {}
            )

            navigation = (
                first_owner.get(
                    "navigationEndpoint",
                    {}
                )
            )

            browse_endpoint = (
                navigation.get(
                    "browseEndpoint",
                    {}
                )
            )

            channel_id = (
                browse_endpoint.get(
                    "browseId"
                )
            )

        duration_text = (
            innertube_video_text(
                item,
                "lengthText"
            )
            or "0:00"
        )

        view_count_text = (
            innertube_video_text(
                item,
                "viewCountText"
            )
        )

        published_text = (
            innertube_video_text(
                item,
                "publishedTimeText"
            )
        )

        webpage_url = (
            "https://www.youtube.com/watch?v="
            + str(video_id)
        )

        videos.append({

            "id":
                video_id,

            "title":
                title,

            "thumbnail":
                innertube_thumbnail(
                    item
                ),

            "duration":
                0,

            "duration_text":
                duration_text,

            "uploader":
                owner,

            "channel":
                owner,

            "channel_id":
                channel_id,

            "view_count":
                view_count_text,

            "upload_date":
                published_text,

            "url":
                webpage_url,

            "webpage_url":
                webpage_url,

            "platform":
                "YouTube"
        })

    return videos


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
            "search-pagination",
            "search-continuation",
            "shorts-search",
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
            "/api/shorts",
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
            or request.args.get("query")
            or data.get("q")
            or data.get("query")
        )

        continuation = (
            request.args.get(
                "continuation"
            )
            or data.get(
                "continuation"
            )
        )

        if not query and not continuation:

            return jsonify({

                "success": False,

                "error":
                    "Search query is required"
            }), 400

        limit = (
            request.args.get("limit")
            or data.get("limit")
            or 20
        )

        try:
            limit = int(limit)
        except Exception:
            limit = 20

        # Each request can return up to 50.
        # The Android app will request the next
        # continuation when the user scrolls.
        limit = max(
            1,
            min(limit, 50)
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

        videos = []
        search_method = None
        next_continuation = None
        diagnostic = {}

        # -----------------------------------------------------
        # CONTINUATION SEARCH
        # -----------------------------------------------------

        if continuation:

            try:

                result = (
                    youtube_innertube_search(
                        query or "",
                        limit,
                        continuation=continuation
                    )
                )

                videos = parse_innertube_results(
                    result.get(
                        "videos",
                        []
                    )
                )

                next_continuation = (
                    result.get(
                        "continuation"
                    )
                )

                search_method = (
                    "youtube_innertube_continuation"
                )

                diagnostic[
                    "continuation_count"
                ] = len(videos)

            except Exception as continuation_error:

                diagnostic[
                    "continuation_error"
                ] = clean_error(
                    continuation_error
                )

        # -----------------------------------------------------
        # FIRST SEARCH
        # -----------------------------------------------------

        if not continuation and not videos:

            try:

                inner_result = (
                    youtube_innertube_search(
                        query,
                        limit
                    )
                )

                inner_renderers = (
                    inner_result.get(
                        "videos",
                        []
                    )
                )

                videos = (
                    parse_innertube_results(
                        inner_renderers
                    )
                )

                next_continuation = (
                    inner_result.get(
                        "continuation"
                    )
                )

                if videos:

                    search_method = (
                        "youtube_innertube"
                    )

                    diagnostic[
                        "innertube_count"
                    ] = len(videos)

                else:

                    diagnostic[
                        "innertube_count"
                    ] = 0

            except Exception as inner_error:

                diagnostic[
                    "innertube_error"
                ] = clean_error(
                    inner_error
                )

        # -----------------------------------------------------
        # FALLBACK YTSEARCH
        # -----------------------------------------------------

        if not videos and not continuation:

            search_query = (
                f"ytsearch{limit}:{query}"
            )

            options = get_ydl_options()

            options[
                "extract_flat"
            ] = "in_playlist"

            with YoutubeDL(
                options
            ) as ydl:

                result = ydl.extract_info(
                    search_query,
                    download=False
                )

            entries = (
                result.get(
                    "entries",
                    []
                )
                or []
            )

            search_method = "ytsearch"

            diagnostic[
                "ytsearch_count"
            ] = len(entries)

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
                query or "",

            "count":
                len(videos),

            "results":
                videos,

            "continuation":
                next_continuation,

            "has_more":
                bool(
                    next_continuation
                )
        }

        if debug:

            response[
                "diagnostic"
            ] = {

                "search_method":
                    search_method,

                "innertube_count":
                    diagnostic.get(
                        "innertube_count",
                        0
                    ),

                "continuation_count":
                    diagnostic.get(
                        "continuation_count",
                        0
                    ),

                "ytsearch_count":
                    diagnostic.get(
                        "ytsearch_count",
                        0
                    ),

                "innertube_error":
                    diagnostic.get(
                        "innertube_error"
                    ),

                "continuation_error":
                    diagnostic.get(
                        "continuation_error"
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

            response[
                "diagnostic"
            ] = {

                "exception_type":
                    type(e).__name__,

                "error":
                    clean_error(e)
            }

        return jsonify(
            response
        ), 500


# =========================================================
# SHORTS SEARCH
# =========================================================

@app.route(
    "/api/shorts",
    methods=["GET", "POST"]
)
def shorts_search():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        query = (
            request.args.get("q")
            or request.args.get("query")
            or data.get("q")
            or data.get("query")
        )

        continuation = (
            request.args.get(
                "continuation"
            )
            or data.get(
                "continuation"
            )
        )

        if not query and not continuation:

            return jsonify({

                "success": False,

                "error":
                    "Search query is required"
            }), 400

        limit = (
            request.args.get("limit")
            or data.get("limit")
            or 5
        )

        try:
            limit = int(limit)
        except Exception:
            limit = 5

        limit = max(
            1,
            min(limit, 20)
        )

        result = (
            youtube_innertube_search(
                query or "",
                limit,
                continuation=continuation,
                shorts=True
            )
        )

        videos = parse_innertube_results(
            result.get(
                "videos",
                []
            )
        )

        return jsonify({

            "success": True,

            "query":
                query or "",

            "count":
                len(videos),

            "results":
                videos,

            "continuation":
                result.get(
                    "continuation"
                ),

            "has_more":
                bool(
                    result.get(
                        "continuation"
                    )
                )
        })

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                clean_error(e)

        }), 500


# =========================================================
# OLD API COMPATIBILITY
# =========================================================

@app.route(
    "/search",
    methods=["GET", "POST"]
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
