import os
import re
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
)


# ============================================================
# MAYOTUBE ADMIN CMS
# Separate Admin CMS module
# ============================================================

admin_cms = Blueprint(
    "admin_cms",
    __name__
)


# ============================================================
# CONFIGURATION
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


try:
    from vercel.blob import BlobClient
except Exception:
    BlobClient = None


# ============================================================
# ALLOWED CMS TYPES
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
    "channel",
]


# ============================================================
# LOCAL LEGACY HOME CONTENT
# ============================================================

HOME_CONTENT_FILE = (
    Path(__file__).resolve().parent
    / "home_content.json"
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


def safe_int(
    value,
    default=0
):

    try:

        if value is None:
            return default

        return int(value)

    except Exception:

        return default


def utc_now():

    return datetime.now(
        timezone.utc
    ).isoformat()


def generate_id(
    prefix="item"
):

    return (
        prefix
        + "_"
        + uuid.uuid4().hex
    )


# ============================================================
# LEGACY HOME CONTENT
# ============================================================

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
# DEFAULT CMS CONTENT
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
# VERCEL BLOB HELPERS
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

        "url":
            "url",

        "downloadUrl":
            "download_url",

        "pathname":
            "pathname",

        "contentType":
            "content_type",

        "etag":
            "etag",

        "size":
            "size",

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
            access="private"
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
        access="private",
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
        content.get(
            "items"
        ),
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
# ADMIN PANEL
# ============================================================

@admin_cms.route(
    "/admin",
    methods=["GET"]
)
def admin_panel():

    return render_template(
        "admin.html"
    )


# ============================================================
# ADMIN STATUS
# ============================================================

@admin_cms.route(
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
# GET ALL CONTENT
# ============================================================

@admin_cms.route(
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
# CREATE CONTENT
# ============================================================

@admin_cms.route(
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
# UPDATE CONTENT
# ============================================================

@admin_cms.route(
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
# DELETE CONTENT
# ============================================================

@admin_cms.route(
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
# TOGGLE CONTENT
# ============================================================

@admin_cms.route(
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
# TOGGLE HOME CMS
# ============================================================

@admin_cms.route(
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
# MEDIA TYPE CHECK
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

    return any(
        filename.endswith(
            ext
        )
        for ext in (
            image_extensions
            + video_extensions
            + audio_extensions
        )
    )


# ============================================================
# MEDIA UPLOAD
# ============================================================

@admin_cms.route(
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
            access="private",
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
# MEDIA LIST
# ============================================================

@admin_cms.route(
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
# MEDIA DELETE
# ============================================================

@admin_cms.route(
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
# INITIALIZE CMS CONTENT
# ============================================================

@admin_cms.route(
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
# HOME CONTENT API
# ============================================================

@admin_cms.route(
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
# HOME CONTENT HEALTH
# ============================================================

@admin_cms.route(
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
            (
                "Vercel Blob CMS"
                if blob_is_configured()
                else "home_content.json"
            ),

        "blob_configured":
            blob_is_configured(),

        "legacy_file_exists":
            HOME_CONTENT_FILE.exists(),

        "content_path":
            CMS_CONTENT_PATH,

    })


# ============================================================
# BLUEPRINT EXPORT
# ============================================================

__all__ = [
    "admin_cms",
]
