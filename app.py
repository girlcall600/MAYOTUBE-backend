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

app = Flask(name)

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

session_token = session.get(
    "admin_api_token",
    ""
)

return bool(
    api_token
    and session_token
    and hmac.compare_digest(
        api_token,
        session_token
    )
)

def empty_content():
return {
"app": "MAYOTUBE",
"count": 0,
"enabled": True,
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
result, expected_size = save_content(
data
)

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
            and
            saved_size == expected_size
        ):
            return result

    except Exception as e:
        last_error = e

    if attempt < 4:
        time.sleep(0.5)

if last_error:
    raise RuntimeError(
        "Blob write completed, but "
        "stored Blob verification failed: "
        + str(last_error)
    )

raise RuntimeError(
    "Blob write completed, but "
    "stored Blob metadata could not be verified"
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

    enabled_items = [
        item
        for item in items
        if isinstance(item, dict)
        and item.get(
            "enabled",
            True
        ) is True
    ]

    return jsonify({
        "app": "MAYOTUBE",
        "count": len(enabled_items),
        "enabled": True,
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

    numeric_ids = [
        int(x.get("id", 0))
        for x in data["items"]
        if isinstance(x, dict)
        and str(
            x.get("id", "")
        ).isdigit()
    ]

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

    save_and_verify(
        data
    )

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

    for index, old_item in enumerate(
        items
    ):
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

    save_and_verify(
        data
    )

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

    save_and_verify(
        data
    )

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

    save_and_verify(
        data
    )

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
        or
        "application/octet-stream"
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

<!DOCTYPE html><html>
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
input{border:1px solid #ccc}
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
"""@app.post("/admin/login")
def admin_login_post():
token = request.form.get(
"token",
""
)

if (
    ADMIN_TOKEN
    and
    hmac.compare_digest(
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
""", 401@app.get("/admin/dashboard")
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
