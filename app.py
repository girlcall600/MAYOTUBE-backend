import os
import json
import hmac
import urllib.request
import urllib.error
from flask import Flask, jsonify, request, session, redirect, url_for

app = Flask(__name__)

ADMIN_TOKEN = os.getenv("MAYOTUBE_ADMIN_TOKEN", "")
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN", "")
BLOB_PATH = "mayotube/home-content.json"
BLOB_BASE = "https://blob.vercel-storage.com"

app.secret_key = ADMIN_TOKEN or os.urandom(32)


def blob_request(method, data=None):
    url = f"{BLOB_BASE}/{BLOB_PATH}"

    headers = {
        "Authorization": f"Bearer {BLOB_TOKEN}",
        "x-api-version": "7"
    }

    if method == "PUT":
        headers.update({
            "Content-Type": "application/json",
            "x-content-type": "application/json",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1"
        })

    req = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers=headers
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def load_content():
    if not BLOB_TOKEN:
        return {
            "app": "MAYOTUBE",
            "count": 0,
            "enabled": True,
            "items": []
        }

    try:
        raw = blob_request("GET")
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {
            "app": "MAYOTUBE",
            "count": 0,
            "enabled": True,
            "items": []
        }


def save_content(data):
    raw = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    blob_request("PUT", raw)


def admin_required():
    return session.get("admin") is True


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


@app.get("/api/admin/content")
def admin_content():

    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    return jsonify(load_content())


@app.post("/api/admin/content/save")
def admin_content_save():

    if not admin_required():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    if not BLOB_TOKEN:
        return jsonify({
            "error": "BLOB_READ_WRITE_TOKEN is not configured"
        }), 500

    try:
        item = request.get_json(silent=True)

        if not isinstance(item, dict):
            return jsonify({
                "error": "Invalid content data"
            }), 400

        content_type = str(item.get("type", "")).strip()

        if not content_type:
            return jsonify({
                "error": "Content type is required"
            }), 400

        data = load_content()

        if not isinstance(data.get("items"), list):
            data["items"] = []

        item["id"] = len(data["items"]) + 1
        item["enabled"] = True

        data["items"].append(item)
        data["count"] = len(data["items"])
        data["enabled"] = True

        save_content(data)

        return jsonify({
            "success": True,
            "message": "Content saved successfully",
            "data": data
        })

    except Exception as e:
        return jsonify({
            "error": "Content save failed",
            "details": str(e)[:200]
        }), 500


@app.get("/admin")
def admin_login():

    if admin_required():
        return redirect(url_for("admin_dashboard"))

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAYOTUBE Admin</title>

<style>
html,body{
    margin:0;
    padding:0;
    width:100%;
    max-width:100%;
    overflow-x:hidden;
}
*{
    box-sizing:border-box;
}
body{
    font-family:Arial,sans-serif;
    background:#f2f2f2;
    padding:30px 15px;
}
.box{
    width:100%;
    max-width:420px;
    min-width:0;
    margin:50px auto;
    background:white;
    padding:25px;
    border-radius:14px;
    box-shadow:0 4px 15px #bbb;
}
h2{
    width:100%;
    margin:0 0 20px;
    text-align:center;
}
input,button{
    display:block;
    width:100%;
    max-width:100%;
    min-width:0;
    padding:13px;
    margin-top:12px;
    border-radius:8px;
}
input{
    border:1px solid #ccc;
}
button{
    border:0;
    background:#111;
    color:white;
    font-size:16px;
}
</style>
</head>

<body>

<div class="box">

<h2>MAYOTUBE ADMIN</h2>

<form method="post" action="/admin/login">

<input
type="password"
name="token"
placeholder="Owner Admin Token"
required>

<button type="submit">
Login
</button>

</form>

</div>

</body>
</html>
"""


@app.post("/admin/login")
def admin_login_post():

    token = request.form.get("token", "")

    if ADMIN_TOKEN and hmac.compare_digest(token, ADMIN_TOKEN):
        session["admin"] = True
        return redirect(url_for("admin_dashboard"))

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
        return redirect(url_for("admin_login"))

    return """
<!DOCTYPE html>
<html>

<head>

<meta
name="viewport"
content="width=device-width,initial-scale=1">

<title>MAYOTUBE Admin Dashboard</title>

<style>

html,
body{
    margin:0;
    padding:0;
    width:100%;
    max-width:100%;
    overflow-x:hidden;
}

*{
    box-sizing:border-box;
}

body{
    font-family:Arial,sans-serif;
    background:#f2f2f2;
    padding:15px;
}

.box{
    width:100%;
    max-width:700px;
    min-width:0;
    margin:0 auto;
}

.header{
    width:100%;
    background:#111;
    color:white;
    padding:20px;
    border-radius:14px;
    margin-bottom:15px;
    text-align:center;
}

.header h2{
    width:100%;
    margin:0 0 10px;
    text-align:center;
}

.card{
    width:100%;
    min-width:0;
    background:white;
    padding:20px;
    margin-bottom:12px;
    border-radius:14px;
    box-shadow:0 2px 8px #ccc;
}

.card h3{
    width:100%;
    margin:0 0 18px;
    text-align:center !important;
}

.field{
    width:100%;
    min-width:0;
    margin-top:18px;
}

.field-title{
    display:block;
    width:100%;
    margin:0 0 8px;
    text-align:center !important;
    font-weight:bold;
    font-size:16px;
    line-height:1.4;
    overflow-wrap:anywhere;
    word-break:break-word;
}

input,
textarea,
select,
button{
    display:block;
    width:100%;
    max-width:100%;
    min-width:0;
    padding:12px;
    margin:0;
    border-radius:8px;
    font-size:15px;
}

input,
textarea,
select{
    border:1px solid #ccc;
    background:white;
}

textarea{
    min-height:100px;
    resize:vertical;
}

button{
    border:0;
    background:#111;
    color:white;
    font-size:16px;
    cursor:pointer;
}

.save{
    margin-top:20px;
    background:#111;
}

.load{
    margin-top:10px;
    background:#555;
}

.status{
    width:100%;
    text-align:center !important;
    font-weight:bold;
}

.success{
    color:green;
}

.error{
    color:red;
}

.type-info{
    width:100%;
    margin-top:15px;
    padding:12px;
    background:#f5f5f5;
    border-radius:8px;
    text-align:center !important;
    overflow-wrap:anywhere;
    word-break:break-word;
}

.saved-item{
    width:100%;
    margin-top:10px;
    padding:12px;
    background:#f7f7f7;
    border-radius:8px;
    overflow-wrap:anywhere;
    word-break:break-word;
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
    border-radius:8px;
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

<h3>
Add Homepage Content
</h3>


<div class="field">

<div class="field-title">
Content Type
</div>

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

<button
class="save"
onclick="saveContent()">

Save Content

</button>

<div
id="message"
class="status"
style="margin-top:12px">
</div>

</div>


<div class="card">

<h3>
Saved Homepage Content
</h3>

<div id="savedContent">
Loading...
</div>

<button
class="load"
onclick="loadContent()">

Reload Saved Content

</button>

</div>


<div class="card">

<h3>
System Status
</h3>

<p class="status success">
Backend Online ✓
</p>

<p class="status success">
Admin Authenticated ✓
</p>

</div>


<a
class="logout"
href="/admin/logout">

Logout

</a>

</div>


<script>

function field(title,html){

    return `
    <div class="field">
        <div class="field-title">${title}</div>
        ${html}
    </div>
    `;

}


const fields = {

url:

field(
"URL",
`
<input
name="url"
placeholder="https://example.com">
`
)

+

field(
"Button Text",
`
<input
name="button_text"
placeholder="Open">
`
),


youtube:

field(
"YouTube URL",
`
<input
name="youtube_url"
placeholder="https://youtube.com/watch?v=...">
`
)

+

field(
"Title",
`
<input
name="title"
placeholder="Video Title">
`
)

+

field(
"Description",
`
<textarea
name="description"
placeholder="Video Description"></textarea>
`
)

+

field(
"Thumbnail URL",
`
<input
name="thumbnail_url"
placeholder="https://...">
`
)

+

field(
"Button Text",
`
<input
name="button_text"
placeholder="Watch">
`
),


message:

field(
"Message",
`
<textarea
name="message"
placeholder="Write your message"></textarea>
`
)

+

field(
"Button Text",
`
<input
name="button_text"
placeholder="Open">
`
)

+

field(
"Button URL",
`
<input
name="button_url"
placeholder="https://...">
`
),


donation:

field(
"Donation Message",
`
<textarea
name="donation_message"
placeholder="Support MAYOTUBE"></textarea>
`
)

+

field(
"Donation URL",
`
<input
name="donation_url"
placeholder="https://...">
`
)

+

field(
"Button Text",
`
<input
name="button_text"
placeholder="Donate">
`
),


audio:

field(
"Audio URL",
`
<input
name="audio_url"
placeholder="https://...">
`
)

+

field(
"Audio Title",
`
<input
name="title"
placeholder="Audio Title">
`
)

+

field(
"Cover Image URL",
`
<input
name="cover_url"
placeholder="https://...">
`
),


notification:

field(
"Notification Message",
`
<textarea
name="notification"
placeholder="Notification text"></textarea>
`
)

+

field(
"Button Text",
`
<input
name="button_text"
placeholder="Open">
`
)

+

field(
"Button URL",
`
<input
name="button_url"
placeholder="https://...">
`
),


image:

field(
"Image URL",
`
<input
name="image_url"
placeholder="https://...">
`
)

+

field(
"Title",
`
<input
name="title"
placeholder="Image Title">
`
)

+

field(
"Click URL",
`
<input
name="click_url"
placeholder="https://...">
`
),


video:

field(
"Video URL",
`
<input
name="video_url"
placeholder="https://...">
`
)

+

field(
"Title",
`
<input
name="title"
placeholder="Video Title">
`
)

+

field(
"Thumbnail URL",
`
<input
name="thumbnail_url"
placeholder="https://...">
`
)

+

field(
"Description",
`
<textarea
name="description"
placeholder="Video Description"></textarea>
`
),


gif:

field(
"GIF URL",
`
<input
name="gif_url"
placeholder="https://...">
`
)

+

field(
"Title",
`
<input
name="title"
placeholder="GIF Title">
`
)

+

field(
"Click URL",
`
<input
name="click_url"
placeholder="https://...">
`
),


ad:

field(
"Advertisement Image/Media URL",
`
<input
name="media_url"
placeholder="https://...">
`
)

+

field(
"Advertisement URL",
`
<input
name="ad_url"
placeholder="https://...">
`
)

+

field(
"Ad Title",
`
<input
name="title"
placeholder="Advertisement">
`
),


music:

field(
"Music URL",
`
<input
name="music_url"
placeholder="https://...">
`
)

+

field(
"Music Title",
`
<input
name="title"
placeholder="Music Title">
`
)

+

field(
"Artist",
`
<input
name="artist"
placeholder="Artist Name">
`
),


gallery:

field(
"Gallery Video URL",
`
<input
name="video_url"
placeholder="https://...">
`
)

+

field(
"Title",
`
<input
name="title"
placeholder="Gallery Video">
`
)

+

field(
"Thumbnail URL",
`
<input
name="thumbnail_url"
placeholder="https://...">
`
),


live:

field(
"Live Channel URL",
`
<input
name="live_url"
placeholder="https://...">
`
)

+

field(
"Channel Name",
`
<input
name="channel_name"
placeholder="Channel Name">
`
)

+

field(
"Thumbnail URL",
`
<input
name="thumbnail_url"
placeholder="https://...">
`
)

};


function showFields(){

    const type =
        document.getElementById("contentType").value;

    const box =
        document.getElementById("fields");

    if(!type){

        box.innerHTML="";

        return;

    }

    box.innerHTML =
        `
        <div class="type-info">
        Selected: ${type.toUpperCase()}
        </div>
        `
        +
        fields[type];

}


function collectFields(){

    const type =
        document.getElementById("contentType").value;

    if(!type){
        return null;
    }

    const item = {
        type:type
    };

    document
    .querySelectorAll("#fields input,#fields textarea")
    .forEach(function(el){

        item[el.name] = el.value.trim();

    });

    return item;

}


async function saveContent(){

    const message =
        document.getElementById("message");

    const item =
        collectFields();

    if(!item){

        message.className="status error";

        message.textContent=
            "Please select a Content Type.";

        return;

    }

    message.className="status";

    message.textContent=
        "Saving...";

    try{

        const response =
            await fetch(
                "/api/admin/content/save",
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
                data.error ||
                "Save failed"
            );

        }

        message.className=
            "status success";

        message.textContent=
            "Content saved successfully ✓";

        loadContent();

    }catch(error){

        message.className=
            "status error";

        message.textContent=
            error.message;

    }

}


async function loadContent(){

    const box =
        document.getElementById("savedContent");

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
                data.error ||
                "Load failed"
            );

        }

        if(!data.items ||
           data.items.length===0){

            box.innerHTML=
                '<div class="saved-item">' +
                'No saved content yet.' +
                '</div>';

            return;

        }

        box.innerHTML=
            data.items.map(function(item){

                return `
                <div class="saved-item">
                    <b>
                    ${item.type.toUpperCase()}
                    </b>
                    <br>
                    ID: ${item.id}
                </div>
                `;

            }).join("");

    }catch(error){

        box.innerHTML=
            '<div class="saved-item">' +
            'Load failed: ' +
            error.message +
            '</div>';

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
    return redirect(url_for("admin_login"))
