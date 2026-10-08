import os
import json
import hmac
import urllib.request
import time
import secrets

from flask import (
    Flask,
    jsonify,
    request,
    session,
    redirect,
    url_for,
    render_template
)

from vercel.blob import BlobClient


app = Flask(__name__)

ADMIN_TOKEN = os.getenv("MAYOTUBE_ADMIN_TOKEN", "")
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "")
BLOB_PATH = "mayotube/home-content.json"

app.secret_key = ADMIN_TOKEN or os.urandom(32)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_PATH="/",
    PERMANENT_SESSION_LIFETIME=86400
)


def admin_required():
    if session.get("admin") is True:
        return True

    api_token = request.headers.get(
        "X-MAYOTUBE-ADMIN",
        ""
    )

    authorization = request.headers.get(
        "Authorization",
        ""
    )

    bearer_token = ""
    if authorization.startswith("Bearer "):
        bearer_token = authorization[7:].strip()

    session_token = session.get(
        "admin_api_token",
        ""
    )

    if api_token and session_token and hmac.compare_digest(api_token, session_token):
        return True

    if bearer_token and ADMIN_TOKEN and hmac.compare_digest(bearer_token, ADMIN_TOKEN):
        return True

    if bearer_token and session_token and hmac.compare_digest(bearer_token, session_token):
        return True

    return False


def empty_content():
    return {
        "app": "MAYOTUBE",
        "count": 0,
        "enabled": True,
        "home_enabled": True,
        "items": []
    }


def blob_client():
    if not BLOB_TOKEN:
        raise RuntimeError(
            "BLOB_READ_WRITE_TOKEN is not configured"
        )

    return BlobClient(token=BLOB_TOKEN)


def get_blob_url():
    client = blob_client()

    listing = client.list_objects(
        prefix=BLOB_PATH
    )

    for blob in listing.blobs:
        pathname = getattr(
            blob,
            "pathname",
            ""
        )

        if pathname == BLOB_PATH:
            return getattr(
                blob,
                "url",
                None
            )

    return None


def load_content(blob_url=None):
    if not blob_url:
        blob_url = get_blob_url()

    if not blob_url:
        return empty_content()

    try:
        cache_buster = str(
            int(time.time() * 1000)
        )

        separator = (
            "&"
            if "?" in blob_url
            else "?"
        )

        fresh_url = (
            blob_url
            + separator
            + "v="
            + cache_buster
        )

        with urllib.request.urlopen(
            fresh_url,
            timeout=15
        ) as response:
            raw = response.read()

    except Exception as e:
        raise RuntimeError(
            f"Blob download failed: {e}"
        )

    if not raw:
        return empty_content()

    try:
        data = json.loads(
            raw.decode("utf-8")
        )
    except Exception as e:
        raise RuntimeError(
            f"Saved Blob contains invalid JSON: {e}"
        )

    if not isinstance(data, dict):
        raise RuntimeError(
            "Saved Blob content is not a JSON object"
        )

    if not isinstance(
        data.get("items"),
        list
    ):
        data["items"] = []

    if "home_enabled" not in data:
        data["home_enabled"] = data.get("enabled", True) is not False
    else:
        value = data.get("home_enabled")
        if isinstance(value, str):
            data["home_enabled"] = value.strip().lower() not in {
                "false", "0", "no", "off", "disabled"
            }
        else:
            data["home_enabled"] = value is not False

    # Legacy content compatibility: older records may have stored
    # enabled as 1/0 or as a string instead of a JSON boolean.
    # Normalize those values in memory so old image/video/message posts
    # can appear on Home and behave correctly in the Admin list.
    normalized_items = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue

        if "enabled" not in item:
            item["enabled"] = True
        else:
            value = item.get("enabled")
            if isinstance(value, str):
                item["enabled"] = value.strip().lower() not in {
                    "false", "0", "no", "off", "disabled"
                }
            else:
                item["enabled"] = bool(value)

        normalized_items.append(item)

    data["items"] = normalized_items

    data["count"] = len(
        data["items"]
    )

    return data


def save_content(data):
    client = blob_client()

    raw = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    result = client.put(
        BLOB_PATH,
        raw,
        access="public",
        content_type="application/json",
        add_random_suffix=False,
        overwrite=True,
        cache_control_max_age=60
    )

    if not result:
        raise RuntimeError(
            "Vercel Blob returned no upload result"
        )

    return result, len(raw)


def save_and_verify(data):
    result, expected_size = save_content(data)

    pathname = getattr(
        result,
        "pathname",
        ""
    )

    blob_url = getattr(
        result,
        "url",
        None
    )

    if pathname != BLOB_PATH:
        raise RuntimeError(
            "Blob upload returned an unexpected pathname"
        )

    if not blob_url:
        raise RuntimeError(
            "Blob upload completed but returned no URL"
        )

    client = blob_client()
    last_error = None

    for attempt in range(5):
        try:
            head = client.head(
                BLOB_PATH
            )

            saved_size = getattr(
                head,
                "size",
                None
            )

            saved_pathname = getattr(
                head,
                "pathname",
                ""
            )

            if (
                saved_pathname == BLOB_PATH
                and saved_size == expected_size
            ):
                return result

        except Exception as e:
            last_error = e

        if attempt < 4:
            time.sleep(0.5)

    if last_error:
        raise RuntimeError(
            "Blob write completed, but stored "
            "Blob verification failed: "
            + str(last_error)
        )

    raise RuntimeError(
        "Blob write completed, but stored "
        "Blob metadata could not be verified"
    )


def error_response(message, error):
    return jsonify({
        "error": message,
        "details": str(error)[:1000]
    }), 500


@app.get("/")
def home():
    return jsonify({
        "app": "MAYOTUBE",
        "status": "online"
    })


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "MAYOTUBE backend",
        "blob_configured": bool(BLOB_TOKEN)
    })


@app.get("/api/home/content")
def public_home_content():
    try:
        data = load_content()

        items = data.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):
            items = []

        home_enabled = data.get("home_enabled", True) is not False

        enabled_items = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get(
                "enabled",
                True
            ) is True
        ] if home_enabled else []

        return jsonify({
            "app": "MAYOTUBE",
            "count": len(enabled_items),
            "enabled": home_enabled,
            "items": enabled_items
        })

    except Exception as e:
        return error_response(
            "Home content unavailable",
            e
        )


@app.get("/api/admin/session")
def admin_session():
    if not admin_required():
        return jsonify({
            "authenticated": False
        }), 401

    return jsonify({
        "authenticated": True,
        "api_token": session.get(
            "admin_api_token",
            ""
        )
    })


@app.get("/api/admin/content")
def admin_content():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        return jsonify(
            load_content()
        )

    except Exception as e:
        return error_response(
            "Content load failed",
            e
        )


@app.post("/api/admin/content/save")
def admin_content_save():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        item = request.get_json(
            silent=True
        )

        if not isinstance(
            item,
            dict
        ):
            return jsonify({
                "error": "Invalid content data"
            }), 400

        content_type = str(
            item.get(
                "type",
                ""
            )
        ).strip()

        if not content_type:
            return jsonify({
                "error": "Content type is required"
            }), 400

        data = load_content()

        if not isinstance(
            data.get("items"),
            list
        ):
            data["items"] = []

        numeric_ids = []

        for x in data["items"]:
            if not isinstance(x, dict):
                continue

            value = x.get("id", 0)

            try:
                numeric_ids.append(
                    int(value)
                )
            except Exception:
                pass

        item["id"] = (
            max(numeric_ids or [0]) + 1
        )

        item["enabled"] = True

        data["items"].append(
            item
        )

        data["count"] = len(
            data["items"]
        )

        save_and_verify(data)

        return jsonify({
            "success": True,
            "message":
                "Content saved and verified successfully",
            "data": data
        })

    except Exception as e:
        return error_response(
            "Content save failed",
            e
        )


@app.post("/api/admin/content/update")
def admin_content_update():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        item = request.get_json(
            silent=True
        )

        if not isinstance(
            item,
            dict
        ):
            return jsonify({
                "error": "Invalid content data"
            }), 400

        item_id = item.get("id")

        if item_id is None:
            return jsonify({
                "error": "Content ID is required"
            }), 400

        data = load_content()

        items = data.get(
            "items",
            []
        )

        found = False

        for index, old_item in enumerate(items):
            if str(
                old_item.get("id")
            ) == str(item_id):

                item["id"] = old_item.get(
                    "id"
                )

                item["enabled"] = old_item.get(
                    "enabled",
                    True
                )

                items[index] = item
                found = True
                break

        if not found:
            return jsonify({
                "error": "Content not found"
            }), 404

        data["items"] = items
        data["count"] = len(items)

        save_and_verify(data)

        return jsonify({
            "success": True,
            "message":
                "Content updated and verified successfully",
            "data": data
        })

    except Exception as e:
        return error_response(
            "Content update failed",
            e
        )


@app.post("/api/admin/content/reorder")
def admin_content_reorder():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        body = request.get_json(
            silent=True
        ) or {}

        order = body.get("order")

        if not isinstance(
            order,
            list
        ):
            return jsonify({
                "error":
                    "Order must be an array"
            }), 400

        data = load_content()

        items = data.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):
            items = []

        if len(order) != len(items):
            return jsonify({
                "error":
                    "Order does not match content count"
            }), 400

        item_map = {}

        for item in items:
            if not isinstance(item, dict):
                continue

            item_id = str(
                item.get("id", "")
            )

            if item_id:
                item_map[item_id] = item

        reordered = []

        for item_id in order:

            key = str(item_id)

            if key not in item_map:
                return jsonify({
                    "error":
                        "Invalid content ID in order: "
                        + key
                }), 400

            reordered.append(
                item_map[key]
            )

        if len(reordered) != len(items):
            return jsonify({
                "error":
                    "Some content items are missing"
            }), 400

        data["items"] = reordered
        data["count"] = len(reordered)

        save_and_verify(data)

        return jsonify({
            "success": True,
            "message":
                "Homepage order saved successfully",
            "data": data
        })

    except Exception as e:
        return error_response(
            "Content reorder failed",
            e
        )


@app.post("/api/admin/content/delete")
def admin_content_delete():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        body = request.get_json(
            silent=True
        ) or {}

        item_id = body.get("id")

        if item_id is None:
            return jsonify({
                "error": "Content ID is required"
            }), 400

        data = load_content()

        items = data.get(
            "items",
            []
        )

        new_items = [
            item
            for item in items
            if str(
                item.get("id")
            ) != str(item_id)
        ]

        if len(new_items) == len(items):
            return jsonify({
                "error": "Content not found"
            }), 404

        for index, item in enumerate(
            new_items,
            1
        ):
            item["id"] = index

        data["items"] = new_items
        data["count"] = len(new_items)

        save_and_verify(data)

        return jsonify({
            "success": True,
            "message":
                "Content deleted and verified successfully",
            "data": data
        })

    except Exception as e:
        return error_response(
            "Content delete failed",
            e
        )


@app.post("/api/admin/content/toggle")
def admin_content_toggle():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        body = request.get_json(
            silent=True
        ) or {}

        item_id = body.get("id")

        if item_id is None:
            return jsonify({
                "error": "Content ID is required"
            }), 400

        data = load_content()

        items = data.get(
            "items",
            []
        )

        found = False
        new_status = False

        for item in items:
            if str(
                item.get("id")
            ) == str(item_id):

                item["enabled"] = not bool(
                    item.get(
                        "enabled",
                        True
                    )
                )

                new_status = item[
                    "enabled"
                ]

                found = True
                break

        if not found:
            return jsonify({
                "error": "Content not found"
            }), 404

        data["items"] = items
        data["count"] = len(items)

        save_and_verify(data)

        return jsonify({
            "success": True,
            "enabled": new_status,
            "data": data
        })

    except Exception as e:
        return error_response(
            "Content status update failed",
            e
        )



# -----------------------------------------------------------------------------
# ADMIN API COMPATIBILITY ROUTES
# admin.html uses these REST-style endpoints.  The original /save, /update,
# /delete and /toggle endpoints are kept above for backward compatibility.
# -----------------------------------------------------------------------------


@app.post("/api/admin/content")
def admin_content_create_compat():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        item = request.get_json(silent=True)
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid content data"}), 400

        content_type = str(item.get("type", "")).strip()
        if not content_type:
            return jsonify({"error": "Content type is required"}), 400

        data = load_content()
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        numeric_ids = []
        for existing in items:
            if not isinstance(existing, dict):
                continue
            try:
                numeric_ids.append(int(existing.get("id", 0)))
            except Exception:
                pass

        item["id"] = max(numeric_ids or [0]) + 1
        item["enabled"] = item.get("enabled", True) is not False
        items.append(item)
        data["items"] = items
        data["count"] = len(items)

        save_and_verify(data)
        return jsonify({
            "success": True,
            "message": "Content saved and verified successfully",
            "data": data
        })
    except Exception as e:
        return error_response("Content save failed", e)


@app.put("/api/admin/content/<item_id>")
def admin_content_update_compat(item_id):
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        item = request.get_json(silent=True)
        if not isinstance(item, dict):
            return jsonify({"error": "Invalid content data"}), 400

        data = load_content()
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        found = False
        for index, old_item in enumerate(items):
            if not isinstance(old_item, dict):
                continue
            if str(old_item.get("id")) == str(item_id):
                item["id"] = old_item.get("id")
                item["enabled"] = item.get("enabled", old_item.get("enabled", True)) is not False
                items[index] = item
                found = True
                break

        if not found:
            return jsonify({"error": "Content not found"}), 404

        data["items"] = items
        data["count"] = len(items)
        save_and_verify(data)
        return jsonify({
            "success": True,
            "message": "Content updated and verified successfully",
            "data": data
        })
    except Exception as e:
        return error_response("Content update failed", e)


@app.delete("/api/admin/content/<item_id>")
def admin_content_delete_compat(item_id):
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = load_content()
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        new_items = [
            item for item in items
            if not isinstance(item, dict)
            or str(item.get("id")) != str(item_id)
        ]

        if len(new_items) == len(items):
            return jsonify({"error": "Content not found"}), 404

        for index, item in enumerate(new_items, 1):
            if isinstance(item, dict):
                item["id"] = index

        data["items"] = new_items
        data["count"] = len(new_items)
        save_and_verify(data)
        return jsonify({
            "success": True,
            "message": "Content deleted and verified successfully",
            "data": data
        })
    except Exception as e:
        return error_response("Content delete failed", e)


@app.patch("/api/admin/content/<item_id>/toggle")
def admin_content_toggle_compat(item_id):
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = load_content()
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []

        for item in items:
            if isinstance(item, dict) and str(item.get("id")) == str(item_id):
                item["enabled"] = not bool(item.get("enabled", True))
                data["items"] = items
                data["count"] = len(items)
                save_and_verify(data)
                return jsonify({
                    "success": True,
                    "enabled": item["enabled"],
                    "data": data
                })

        return jsonify({"error": "Content not found"}), 404
    except Exception as e:
        return error_response("Content status update failed", e)


@app.patch("/api/admin/home/toggle")
def admin_home_toggle_compat():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        body = request.get_json(silent=True) or {}
        enabled = bool(body.get("enabled", True))
        data = load_content()
        data["home_enabled"] = enabled
        data["enabled"] = enabled
        data["count"] = len(data.get("items", []))
        save_and_verify(data)
        return jsonify({
            "success": True,
            "enabled": enabled,
            "data": data
        })
    except Exception as e:
        return error_response("Home status update failed", e)


@app.get("/api/admin/media")
def admin_media_list_compat():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        client = blob_client()
        listing = client.list_objects(prefix="media/")
        media = []

        for blob in getattr(listing, "blobs", []) or []:
            pathname = getattr(blob, "pathname", "") or ""
            if not pathname or pathname == "media/":
                continue

            url = getattr(blob, "url", None)
            filename = pathname.rsplit("/", 1)[-1]
            content_type = getattr(blob, "content_type", None) or getattr(blob, "contentType", None) or ""

            media.append({
                "id": pathname,
                "key": pathname,
                "pathname": pathname,
                "name": filename,
                "filename": filename,
                "url": url,
                "public_url": url,
                "content_type": content_type
            })

        return jsonify({"media": media, "count": len(media)})
    except Exception as e:
        return error_response("Media list failed", e)


@app.delete("/api/admin/media/<path:media_id>")
def admin_media_delete_compat(media_id):
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        pathname = media_id
        if not pathname.startswith("media/"):
            pathname = "media/" + pathname

        client = blob_client()
        delete_method = getattr(client, "delete", None)
        if not callable(delete_method):
            raise RuntimeError("Installed Vercel Blob SDK does not provide delete()")

        delete_method(pathname)
        return jsonify({
            "success": True,
            "message": "Media deleted successfully",
            "pathname": pathname
        })
    except Exception as e:
        return error_response("Media delete failed", e)


@app.get("/api/admin/status")
def admin_status_compat():
    if not admin_required():
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = load_content()
        items = data.get("items", []) if isinstance(data, dict) else []
        return jsonify({
            "success": True,
            "app": "MAYOTUBE",
            "status": "online",
            "content_count": len(items) if isinstance(items, list) else 0,
            "home_enabled": data.get("home_enabled", True) is not False,
            "blob_configured": bool(BLOB_TOKEN),
            "admin_token_configured": bool(ADMIN_TOKEN)
        })
    except Exception as e:
        return error_response("Status unavailable", e)


@app.post("/api/admin/media")
@app.post("/api/admin/media/upload")
def admin_media_upload():
    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        file = request.files.get(
            "file"
        )

        if not file:
            return jsonify({
                "error": "No file uploaded"
            }), 400

        filename = (
            file.filename or ""
        ).strip()

        if not filename:
            return jsonify({
                "error": "Filename is required"
            }), 400

        filename = os.path.basename(
            filename
        )

        extension = os.path.splitext(
            filename
        )[1].lower()

        allowed = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".mp4",
            ".webm",
            ".mov",
            ".mp3",
            ".wav",
            ".m4a",
            ".aac"
        }

        if extension not in allowed:
            return jsonify({
                "error":
                    "File type is not allowed"
            }), 400

        file_data = file.read()

        if not file_data:
            return jsonify({
                "error": "Empty file"
            }), 400

        max_size = 4 * 1024 * 1024

        if len(file_data) > max_size:
            return jsonify({
                "error":
                    "File is larger than 4 MB."
            }), 413

        content_type = (
            file.mimetype
            or "application/octet-stream"
        )

        client = blob_client()

        result = client.put(
            f"media/{filename}",
            file_data,
            access="public",
            content_type=content_type,
            add_random_suffix=True
        )

        return jsonify({
            "success": True,
            "message":
                "Media uploaded successfully",
            "url": result.url,
            "pathname":
                result.pathname,
            "content_type":
                result.content_type,
            "filename":
                filename
        })

    except Exception as e:
        return error_response(
            "Media upload failed",
            e
        )


@app.get("/admin")
def admin_login():
    if admin_required():
        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport"
content="width=device-width,initial-scale=1">
<title>MAYOTUBE Admin</title>
<style>
html,body{
margin:0;
padding:0;
width:100%;
max-width:100%;
overflow-x:hidden
}
*{box-sizing:border-box}
body{
font-family:Arial,sans-serif;
background:#f2f2f2;
padding:30px 15px
}
.box{
width:100%;
max-width:420px;
margin:50px auto;
background:white;
padding:25px;
border-radius:14px;
box-shadow:0 4px 15px #bbb
}
h2{
margin:0 0 20px;
text-align:center
}
input,button{
display:block;
width:100%;
padding:13px;
margin-top:12px;
border-radius:8px
}
input{
border:1px solid #ccc
}
button{
border:0;
background:#111;
color:white;
font-size:16px
}
</style>
</head>
<body>
<div class="box">
<h2>MAYOTUBE ADMIN</h2>
<form method="post" action="/admin/login">
<input type="password"
name="token"
placeholder="Owner Admin Token"
required>
<button type="submit">Login</button>
</form>
</div>
</body>
</html>
"""


@app.post("/admin/login")
def admin_login_post():
    token = request.form.get(
        "token",
        ""
    )

    if (
        ADMIN_TOKEN
        and hmac.compare_digest(
            token,
            ADMIN_TOKEN
        )
    ):
        session.clear()

        session["admin"] = True

        session["admin_api_token"] = (
            secrets.token_urlsafe(32)
        )

        session.permanent = True

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    return """
<h3 style="text-align:center;color:red">
Invalid Admin Token
</h3>
<p style="text-align:center">
<a href="/admin">Try Again</a>
</p>
""", 401


@app.get("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(
            url_for(
                "admin_login"
            )
        )

    return render_template(
        "admin.html"
    )


@app.get("/admin/logout")
def admin_logout():
    session.clear()

    return redirect(
        url_for(
            "admin_login"
        )
    )
