import os
import json
import hmac

from flask import (
    Flask,
    jsonify,
    request,
    session,
    redirect,
    url_for
)

from vercel.blob import BlobClient


app = Flask(__name__)

ADMIN_TOKEN = os.getenv("MAYOTUBE_ADMIN_TOKEN", "")
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "")
BLOB_PATH = "mayotube/home-content.json"

app.secret_key = ADMIN_TOKEN or os.urandom(32)


# =========================================================
# HELPERS
# =========================================================

def admin_required():
    return session.get("admin") is True


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
    return BlobClient()


def load_content():
    client = blob_client()

    result = client.get(
        BLOB_PATH,
        access="public",
        token=BLOB_TOKEN
    )

    if result is None:
        return empty_content()

    if result.status_code != 200:
        raise RuntimeError(
            f"Blob read returned status {result.status_code}"
        )

    if result.stream is None:
        raise RuntimeError(
            "Blob returned no content stream"
        )

    raw = b"".join(result.stream)

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
        token=BLOB_TOKEN
    )

    if not result:
        raise RuntimeError(
            "Vercel Blob returned no upload result"
        )

    return result


def save_and_verify(data):
    result = save_content(data)

    saved = load_content()

    if saved != data:
        raise RuntimeError(
            "Blob write completed but verification failed"
        )

    return result


def error_response(message, error):
    return jsonify({
        "error": message,
        "details": str(error)[:1000]
    }), 500


# =========================================================
# PUBLIC HOME
# =========================================================

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


# =========================================================
# ADMIN CONTENT
# =========================================================

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

        data["items"].append(item)
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


# =========================================================
# MEDIA UPLOAD
# =========================================================

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
            file.mimetype or
            "application/octet-stream"
        )

        client = blob_client()

        result = client.put(
            f"media/{filename}",
            file_data,
            access="public",
            content_type=content_type,
            add_random_suffix=True,
            token=BLOB_TOKEN
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


# =========================================================
# ADMIN LOGIN
# =========================================================

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
"""


@app.post("/admin/login")
def admin_login_post():

    token = request.form.get(
        "token",
        ""
    )

    if ADMIN_TOKEN and hmac.compare_digest(
        token,
        ADMIN_TOKEN
    ):
        session["admin"] = True

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


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.get("/admin/dashboard")
def admin_dashboard():

    if not admin_required():
        return redirect(
            url_for(
                "admin_login"
            )
        )

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport"
content="width=device-width,initial-scale=1">
<title>MAYOTUBE Admin Dashboard</title>
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
padding:15px
}
.box{
width:100%;
max-width:700px;
margin:0 auto
}
.header{
background:#111;
color:white;
padding:20px;
border-radius:14px;
margin-bottom:15px;
text-align:center
}
.header h2{margin:0 0 10px}
.card{
width:100%;
background:white;
padding:20px;
margin-bottom:12px;
border-radius:14px;
box-shadow:0 2px 8px #ccc;
overflow:hidden
}
.card h3{
margin:0 0 18px;
text-align:center!important
}
.field{
width:100%;
margin-top:18px
}
.field-title{
display:block;
width:100%;
margin:0 0 8px;
text-align:center!important;
font-weight:bold;
font-size:16px;
line-height:1.4;
overflow-wrap:anywhere;
word-break:break-word
}
input,textarea,select,button{
display:block;
width:100%;
max-width:100%;
min-width:0;
padding:12px;
margin:0;
border-radius:8px;
font-size:15px
}
input,textarea,select{
border:1px solid #ccc;
background:white
}
textarea{
min-height:100px;
resize:vertical
}
button{
border:0;
background:#111;
color:white;
font-size:16px;
cursor:pointer
}
.save{margin-top:20px}
.load{
margin-top:12px;
background:#555
}
.status{
text-align:center;
font-weight:bold
}
.success{color:green}
.error{color:red}
.type-info{
margin-top:15px;
padding:12px;
background:#f5f5f5;
border-radius:8px;
text-align:center;
overflow-wrap:anywhere
}
.saved-item{
width:100%;
margin-top:12px;
padding:15px;
background:#f7f7f7;
border-radius:10px;
overflow-wrap:anywhere;
word-break:break-word
}
.saved-title{
text-align:center;
font-weight:bold;
margin-bottom:10px
}
.action-row{
display:flex;
gap:8px;
margin-top:12px
}
.action-row button{
flex:1;
margin:0
}
.edit{background:#444}
.delete{background:#b00020}
.toggle{background:#087f23}
.disabled{opacity:.6}
.upload-box{
margin-top:20px;
padding:15px;
background:#f7f7f7;
border-radius:10px
}
.upload-box input{margin-top:10px}
.upload-btn{margin-top:12px}
.upload-result{
margin-top:12px;
font-size:14px;
word-break:break-all;
overflow-wrap:anywhere
}
.logout{
display:block;
width:100%;
margin-top:15px;
padding:12px;
background:#ddd;
color:#111;
text-decoration:none;
text-align:center;
border-radius:8px
}
</style>
</head>

<body>
<div class="box">

<div class="header">
<h2>MAYOTUBE ADMIN</h2>
<div class="status success">
Owner Admin ✓
</div>
</div>

<div class="card">
<h3>Add Homepage Content</h3>

<div class="field">
<div class="field-title">Content Type</div>

<select id="contentType"
onchange="showFields()">

<option value="">
Select Content Type
</option>

<option value="url">
URL / Web Link
</option>

<option value="youtube">
YouTube Video
</option>

<option value="message">
Message
</option>

<option value="donation">
Donation
</option>

<option value="audio">
Audio
</option>

<option value="notification">
Notification
</option>

<option value="image">
Image
</option>

<option value="video">
Video
</option>

<option value="gif">
GIF
</option>

<option value="ad">
Advertisement
</option>

<option value="music">
Music Link
</option>

<option value="gallery">
Gallery Video
</option>

<option value="live">
Live Channel
</option>

</select>
</div>

<div id="fields"></div>

<button class="save"
onclick="saveContent()">
Save Content
</button>

<div id="message"
class="status"
style="margin-top:12px">
</div>

</div>

<div class="card">
<h3>Media Upload</h3>

<div class="upload-box">
<div class="field-title">
Select Image / Video / GIF / Audio
</div>

<input id="mediaFile"
type="file"
accept="image/*,video/*,audio/*">

<button class="upload-btn"
onclick="uploadMedia()">
Upload Media
</button>

<div id="uploadResult"
class="upload-result">
</div>
</div>
</div>

<div class="card">
<h3>Saved Homepage Content</h3>

<div id="savedContent">
Loading...
</div>

<button class="load"
onclick="loadContent()">
Reload Saved Content
</button>
</div>

<div class="card">
<h3>System Status</h3>

<p class="status success">
Backend Online ✓
</p>

<p class="status success">
Admin Authenticated ✓
</p>
</div>

<a class="logout"
href="/admin/logout">
Logout
</a>

</div>

<script>

let editingId = null;

function field(title,html){
return `
<div class="field">
<div class="field-title">
${title}
</div>
${html}
</div>
`;
}

const fields = {

url:
field(
"URL",
`<input name="url"
placeholder="https://example.com">`
)
+
field(
"Button Text",
`<input name="button_text"
placeholder="Open">`
),

youtube:
field(
"YouTube URL",
`<input name="youtube_url"
placeholder="https://youtube.com/watch?v=...">`
)
+
field(
"Title",
`<input name="title"
placeholder="Video Title">`
)
+
field(
"Description",
`<textarea name="description"
placeholder="Video Description"></textarea>`
)
+
field(
"Thumbnail URL",
`<input name="thumbnail_url"
placeholder="https://...">`
)
+
field(
"Button Text",
`<input name="button_text"
placeholder="Watch">`
),

message:
field(
"Message",
`<textarea name="message"
placeholder="Write your message"></textarea>`
)
+
field(
"Button Text",
`<input name="button_text"
placeholder="Open">`
)
+
field(
"Button URL",
`<input name="button_url"
placeholder="https://...">`
),

donation:
field(
"Donation Message",
`<textarea name="donation_message"
placeholder="Support MAYOTUBE"></textarea>`
)
+
field(
"Donation URL",
`<input name="donation_url"
placeholder="https://...">`
)
+
field(
"Button Text",
`<input name="button_text"
placeholder="Donate">`
),

audio:
field(
"Audio URL",
`<input name="audio_url"
placeholder="https://...">`
)
+
field(
"Audio Title",
`<input name="title"
placeholder="Audio Title">`
)
+
field(
"Cover Image URL",
`<input name="cover_url"
placeholder="https://...">`
),

notification:
field(
"Notification Message",
`<textarea name="notification"
placeholder="Notification text"></textarea>`
)
+
field(
"Button Text",
`<input name="button_text"
placeholder="Open">`
)
+
field(
"Button URL",
`<input name="button_url"
placeholder="https://...">`
),

image:
field(
"Image URL",
`<input name="image_url"
placeholder="https://...">`
)
+
field(
"Title",
`<input name="title"
placeholder="Image Title">`
)
+
field(
"Click URL",
`<input name="click_url"
placeholder="https://...">`
),

video:
field(
"Video URL",
`<input name="video_url"
placeholder="https://...">`
)
+
field(
"Title",
`<input name="title"
placeholder="Video Title">`
)
+
field(
"Thumbnail URL",
`<input name="thumbnail_url"
placeholder="https://...">`
)
+
field(
"Description",
`<textarea name="description"
placeholder="Video Description"></textarea>`
),

gif:
field(
"GIF URL",
`<input name="gif_url"
placeholder="https://...">`
)
+
field(
"Title",
`<input name="title"
placeholder="GIF Title">`
)
+
field(
"Click URL",
`<input name="click_url"
placeholder="https://...">`
),

ad:
field(
"Advertisement Image/Media URL",
`<input name="media_url"
placeholder="https://...">`
)
+
field(
"Advertisement URL",
`<input name="ad_url"
placeholder="https://...">`
)
+
field(
"Ad Title",
`<input name="title"
placeholder="Advertisement">`
),

music:
field(
"Music URL",
`<input name="music_url"
placeholder="https://...">`
)
+
field(
"Music Title",
`<input name="title"
placeholder="Music Title">`
)
+
field(
"Artist",
`<input name="artist"
placeholder="Artist Name">`
),

gallery:
field(
"Gallery Video URL",
`<input name="video_url"
placeholder="https://...">`
)
+
field(
"Title",
`<input name="title"
placeholder="Gallery Video">`
)
+
field(
"Thumbnail URL",
`<input name="thumbnail_url"
placeholder="https://...">`
),

live:
field(
"Live Channel URL",
`<input name="live_url"
placeholder="https://...">`
)
+
field(
"Channel Name",
`<input name="channel_name"
placeholder="Channel Name">`
)
+
field(
"Thumbnail URL",
`<input name="thumbnail_url"
placeholder="https://...">`
)

};


function showFields(data={}){
const type =
data.type ||
document.getElementById(
"contentType"
).value;

const box =
document.getElementById(
"fields"
);

if(!type){
box.innerHTML="";
return;
}

document.getElementById(
"contentType"
).value=type;

box.innerHTML=
`
<div class="type-info">
Selected:
${type.toUpperCase()}
</div>
`
+
fields[type];

Object.keys(data).forEach(
function(key){

const el =
box.querySelector(
`[name="${key}"]`
);

if(el){
el.value =
data[key] ?? "";
}

}
);
}


function collectFields(){

const type =
document.getElementById(
"contentType"
).value;

if(!type){
return null;
}

const item={
type:type
};

document
.querySelectorAll(
"#fields input,#fields textarea"
)
.forEach(
function(el){

item[el.name]=
el.value.trim();

}
);

if(editingId !== null){
item.id=editingId;
}

return item;
}


async function saveContent(){

const message =
document.getElementById(
"message"
);

const item =
collectFields();

if(!item){

message.className=
"status error";

message.textContent=
"Please select a Content Type.";

return;
}

message.className="status";
message.textContent="Saving and verifying...";

const endpoint =
editingId === null
? "/api/admin/content/save"
: "/api/admin/content/update";

try{

const response =
await fetch(
endpoint,
{
method:"POST",
headers:{
"Content-Type":
"application/json"
},
body:
JSON.stringify(item)
}
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.details
? data.error +
" — " +
data.details
: data.error ||
"Save failed"
);
}

message.className=
"status success";

message.textContent=
editingId === null
? "Content saved and verified ✓"
: "Content updated and verified ✓";

editingId=null;

document.getElementById(
"contentType"
).value="";

document.getElementById(
"fields"
).innerHTML="";

loadContent();

}catch(error){

message.className=
"status error";

message.textContent=
error.message;
}
}


async function uploadMedia(){

const file =
document.getElementById(
"mediaFile"
).files[0];

const result =
document.getElementById(
"uploadResult"
);

if(!file){

result.className=
"upload-result error";

result.textContent=
"Please select a file.";

return;
}

result.className=
"upload-result";

result.textContent=
"Uploading...";

try{

const form =
new FormData();

form.append(
"file",
file
);

const response =
await fetch(
"/api/admin/media/upload",
{
method:"POST",
body:form
}
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.details
? data.error +
" — " +
data.details
: data.error ||
"Upload failed"
);
}

result.className=
"upload-result success";

result.innerHTML=
"Upload successful ✓<br>" +
"URL:<br>" +
data.url;

}catch(error){

result.className=
"upload-result error";

result.textContent=
error.message;
}
}


async function loadContent(){

const box =
document.getElementById(
"savedContent"
);

box.innerHTML="Loading...";

try{

const response =
await fetch(
"/api/admin/content"
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.details
? data.error +
" — " +
data.details
: data.error ||
"Load failed"
);
}

if(
!data.items ||
data.items.length===0
){

box.innerHTML=
`
<div class="saved-item">
No saved content yet.
</div>
`;

return;
}

box.innerHTML =
data.items.map(
function(item){

const status =
item.enabled !== false
? "Enabled"
: "Disabled";

const cls =
item.enabled !== false
? ""
: "disabled";

return `
<div
class="saved-item ${cls}">

<div class="saved-title">
${item.type.toUpperCase()}
</div>

<div>
ID: ${item.id}
</div>

<div>
Status: ${status}
</div>

<div class="action-row">

<button
class="edit"
onclick='editContent(${JSON.stringify(item)})'>
Edit
</button>

<button
class="toggle"
onclick="toggleContent(${item.id})">
${
item.enabled !== false
? "Disable"
: "Enable"
}
</button>

<button
class="delete"
onclick="deleteContent(${item.id})">
Delete
</button>

</div>

</div>
`;
}
).join("");

}catch(error){

box.innerHTML=
`
<div class="saved-item error">
Load failed:
${error.message}
</div>
`;
}
}


function editContent(item){

editingId=item.id;

showFields(item);

window.scrollTo({
top:0,
behavior:"smooth"
});

const message =
document.getElementById(
"message"
);

message.className="status";

message.textContent =
"Editing Content ID " +
item.id;
}


async function deleteContent(id){

if(!confirm(
"Delete this content?"
)){
return;
}

try{

const response =
await fetch(
"/api/admin/content/delete",
{
method:"POST",
headers:{
"Content-Type":
"application/json"
},
body:
JSON.stringify({
id:id
})
}
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.details
? data.error +
" — " +
data.details
: data.error ||
"Delete failed"
);
}

loadContent();

}catch(error){

alert(error.message);
}
}


async function toggleContent(id){

try{

const response =
await fetch(
"/api/admin/content/toggle",
{
method:"POST",
headers:{
"Content-Type":
"application/json"
},
body:
JSON.stringify({
id:id
})
}
);

const data =
await response.json();

if(!response.ok){

throw new Error(
data.details
? data.error +
" — " +
data.details
: data.error ||
"Status update failed"
);
}

loadContent();

}catch(error){

alert(error.message);
}
}


loadContent();

</script>
</body>
</html>
"""


@app.get("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(
        url_for(
            "admin_login"
        )
    )
