import os
import hmac
import json
import uuid
from flask import Flask, jsonify, request, session, redirect, url_for
from vercel.blob import BlobClient

app = Flask(__name__)

ADMIN_TOKEN = os.getenv("MAYOTUBE_ADMIN_TOKEN", "")
app.secret_key = ADMIN_TOKEN or os.urandom(32)

CONTENT_PATH = "cms/home_content.json"


def admin_ok():
    return bool(session.get("admin"))


def blob_client():
    token = os.getenv("BLOB_READ_WRITE_TOKEN", "")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN is missing")
    return BlobClient(token=token)


def default_data():
    return {
        "app": "MAYOTUBE",
        "count": 0,
        "enabled": True,
        "items": []
    }


def read_content():
    client = blob_client()

    try:
        result = client.get(CONTENT_PATH, access="public")

        if not result or result.status_code != 200:
            return default_data()

        data = b"".join(result.stream)
        return json.loads(data.decode("utf-8"))

    except Exception:
        return default_data()


def write_content(data):
    client = blob_client()

    raw = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    blob = client.put(
        CONTENT_PATH,
        raw,
        access="public",
        content_type="application/json",
        allow_overwrite=True
    )

    return blob


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
        "service": "MAYOTUBE backend"
    })


@app.get("/admin")
def admin_login():
    if admin_ok():
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
    overflow:hidden;
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

<button type="submit">Login</button>

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

    if not admin_ok():
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
}

.save{
    margin-top:20px;
    background:#16803c;
}

.load{
    margin-top:10px;
    background:#2457a6;
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

.status{
    width:100%;
    text-align:center !important;
    color:green;
    font-weight:bold;
}

.result{
    width:100%;
    margin-top:15px;
    padding:12px;
    background:#f5f5f5;
    border-radius:8px;
    text-align:center;
    overflow-wrap:anywhere;
    word-break:break-word;
}

.item{
    background:#fafafa;
    border:1px solid #ddd;
    border-radius:10px;
    padding:12px;
    margin-top:10px;
}

.item-title{
    font-weight:bold;
    text-align:center;
}

.item-data{
    margin-top:8px;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
    word-break:break-word;
    font-size:13px;
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

<div class="status">
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

<select id="contentType" onchange="showFields()">

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
Load Content
</button>

</div>


<div class="card">

<h3>
System Status
</h3>

<p class="status">
Backend Online ✓
</p>

<p class="status">
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


const colorFields =
    field(
        "Title Color",
        `<input type="color" name="title_color" value="#111111">`
    )
    +
    field(
        "Message Color",
        `<input type="color" name="message_color" value="#111111">`
    )
    +
    field(
        "Description Color",
        `<input type="color" name="description_color" value="#111111">`
    )
    +
    field(
        "Button Text Color",
        `<input type="color" name="button_text_color" value="#ffffff">`
    )
    +
    field(
        "Button Background Color",
        `<input type="color" name="button_background_color" value="#111111">`
    );


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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
)

+

colorFields,


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

+

colorFields

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
        fields[type]
        +
        `
        <button
        class="save"
        onclick="saveContent()">
        Save Homepage Content
        </button>
        `;

}


async function saveContent(){

    const type =
        document.getElementById("contentType").value;

    if(!type){

        alert("Select Content Type");

        return;

    }

    const data = {
        type:type,
        enabled:true,
        order:Date.now(),
        id:crypto.randomUUID(),
        title:"",
        message:"",
        description:"",
        button_text:"",
        button_url:"",
        url:"",
        youtube_url:"",
        thumbnail_url:"",
        image_url:"",
        video_url:"",
        gif_url:"",
        audio_url:"",
        cover_url:"",
        donation_message:"",
        donation_url:"",
        notification:"",
        click_url:"",
        media_url:"",
        ad_url:"",
        music_url:"",
        artist:"",
        channel_name:"",
        live_url:"",
        title_color:"#111111",
        message_color:"#111111",
        description_color:"#111111",
        button_text_color:"#ffffff",
        button_background_color:"#111111"
    };

    document
        .querySelectorAll("#fields input,#fields textarea")
        .forEach(el => {

            if(el.name){
                data[el.name] = el.value;
            }

        });

    try{

        const response =
            await fetch("/api/admin/content",{

                method:"POST",

                headers:{
                    "Content-Type":"application/json"
                },

                body:JSON.stringify(data)

            });

        const result =
            await response.json();

        if(!response.ok){

            alert(
                result.error ||
                "Save failed"
            );

            return;

        }

        alert("Content Saved ✓");

        loadContent();

    }catch(error){

        alert(
            "Connection error"
        );

    }

}


async function loadContent(){

    const box =
        document.getElementById("savedContent");

    box.innerHTML="Loading...";

    try{

        const response =
            await fetch("/api/admin/content");

        const data =
            await response.json();

        if(!response.ok){

            box.innerHTML =
                "Load failed";

            return;

        }

        if(!data.items || !data.items.length){

            box.innerHTML =
                "No saved content";

            return;

        }

        box.innerHTML =
            data.items.map(item => `

            <div class="item">

                <div class="item-title">
                    ${item.type || "Content"}
                </div>

                <div class="item-data">
${escapeHtml(JSON.stringify(item,null,2))}
                </div>

            </div>

            `).join("");

    }catch(error){

        box.innerHTML =
            "Connection error";

    }

}


function escapeHtml(value){

    return value
        .replaceAll("&","&amp;")
        .replaceAll("<","&lt;")
        .replaceAll(">","&gt;")
        .replaceAll('"',"&quot;")
        .replaceAll("'","&#039;");

}


loadContent();

</script>

</body>

</html>
"""


@app.get("/api/admin/content")
def admin_content_get():

    if not admin_ok():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    try:
        return jsonify(read_content())

    except Exception as e:
        return jsonify({
            "error": "Content load failed",
            "message": str(e)
        }), 500


@app.post("/api/admin/content")
def admin_content_post():

    if not admin_ok():
        return jsonify({
            "error": "Unauthorized"
        }), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON"
        }), 400

    content_type = str(
        data.get("type", "")
    ).strip().lower()

    if not content_type:
        return jsonify({
            "error": "Content type is required"
        }), 400

    content = read_content()

    item = {
        "id": str(
            data.get("id") or uuid.uuid4()
        ),
        "type": content_type,
        "enabled": bool(
            data.get("enabled", True)
        ),
        "order": int(
            data.get("order", 0)
        )
    }

    for key, value in data.items():

        if key in (
            "id",
            "type",
            "enabled",
            "order"
        ):
            continue

        if isinstance(value, (str, int, float, bool)) or value is None:
            item[key] = value

    content["items"].append(item)

    content["count"] = len(
        content["items"]
    )

    write_content(content)

    return jsonify({
        "success": True,
        "message": "Content saved",
        "item": item,
        "count": content["count"]
    })


@app.get("/api/home-content")
def public_home_content():

    try:

        data = read_content()

        if not data.get("enabled", True):
            return jsonify({
                "app": "MAYOTUBE",
                "count": 0,
                "enabled": False,
                "items": []
            })

        items = [
            item for item in data.get("items", [])
            if item.get("enabled", True)
        ]

        items.sort(
            key=lambda item:
            item.get("order", 0)
        )

        return jsonify({
            "app": "MAYOTUBE",
            "count": len(items),
            "enabled": True,
            "items": items
        })

    except Exception as e:

        return jsonify({
            "error": "Home content load failed",
            "message": str(e)
        }), 500


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))
