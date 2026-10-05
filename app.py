import os
import hmac
from flask import Flask, jsonify, request, session, redirect, url_for

app = Flask(__name__)

ADMIN_TOKEN = os.getenv("MAYOTUBE_ADMIN_TOKEN", "")
app.secret_key = ADMIN_TOKEN or os.urandom(32)


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
    if session.get("admin"):
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
    text-align:center;
    margin-top:0;
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
        <input type="password" name="token"
               placeholder="Owner Admin Token" required>
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
<h3 style="text-align:center;color:red">Invalid Admin Token</h3>
<p style="text-align:center">
<a href="/admin">Try Again</a>
</p>
""", 401


@app.get("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAYOTUBE Admin Dashboard</title>

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
    max-width:100%;
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
    margin:auto;
    overflow:hidden;
}

.header{
    width:100%;
    background:#111;
    color:white;
    padding:20px;
    border-radius:14px;
    margin-bottom:15px;
    text-align:center;
    overflow:hidden;
}

.header h2{
    margin:0;
    text-align:center;
    overflow-wrap:anywhere;
    word-break:break-word;
}

.card{
    width:100%;
    min-width:0;
    background:white;
    padding:20px;
    margin-bottom:12px;
    border-radius:14px;
    box-shadow:0 2px 8px #ccc;
    overflow:hidden;
}

h3{
    margin-top:0;
    text-align:center;
    overflow-wrap:anywhere;
    word-break:break-word;
}

label{
    display:block;
    width:100%;
    margin-top:16px;
    font-weight:bold;
    text-align:center;
    overflow-wrap:anywhere;
    word-break:break-word;
}

input,textarea,select,button{
    display:block;
    width:100%;
    max-width:100%;
    min-width:0;
    padding:12px;
    margin-top:7px;
    border-radius:8px;
    font-size:15px;
}

input,textarea,select{
    border:1px solid #ccc;
    background:white;
}

input,textarea{
    overflow-wrap:anywhere;
    word-break:break-word;
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

.status{
    text-align:center;
    color:green;
    font-weight:bold;
    overflow-wrap:anywhere;
    word-break:break-word;
}

.logout{
    display:block;
    width:100%;
    max-width:100%;
    text-align:center;
    margin-top:15px;
    padding:12px;
    background:#ddd;
    color:#111;
    text-decoration:none;
    border-radius:8px;
}

.type-info{
    width:100%;
    max-width:100%;
    background:#f5f5f5;
    padding:12px;
    border-radius:8px;
    margin-top:12px;
    color:#555;
    text-align:center;
    overflow-wrap:anywhere;
    word-break:break-word;
}

.hidden{
    display:none;
}
</style>
</head>

<body>

<div class="box">

<div class="header">
    <h2>MAYOTUBE ADMIN</h2>
    <div class="status">Owner Admin ✓</div>
</div>

<div class="card">

<h3>Add Homepage Content</h3>

<label>Content Type</label>

<select id="contentType" onchange="showFields()">
    <option value="">Select Content Type</option>
    <option value="url">URL / Web Link</option>
    <option value="youtube">YouTube Video</option>
    <option value="message">Message</option>
    <option value="donation">Donation</option>
    <option value="audio">Audio</option>
    <option value="notification">Notification</option>
    <option value="image">Image</option>
    <option value="video">Video</option>
    <option value="gif">GIF</option>
    <option value="ad">Advertisement</option>
    <option value="music">Music Link</option>
    <option value="gallery">Gallery Video</option>
    <option value="live">Live Channel</option>
</select>

<div id="fields"></div>

</div>

<div class="card">
    <h3>System Status</h3>
    <p class="status">Backend Online ✓</p>
    <p class="status">Admin Authenticated ✓</p>
</div>

<a class="logout" href="/admin/logout">Logout</a>

</div>

<script>

const fields = {

url: `
<label>URL</label>
<input name="url" placeholder="https://example.com">

<label>Button Text</label>
<input name="button_text" placeholder="Open">
`,

youtube: `
<label>YouTube URL</label>
<input name="youtube_url"
placeholder="https://youtube.com/watch?v=...">

<label>Title</label>
<input name="title" placeholder="Video Title">

<label>Description</label>
<textarea name="description"
placeholder="Video Description"></textarea>

<label>Thumbnail URL</label>
<input name="thumbnail_url"
placeholder="https://...">

<label>Button Text</label>
<input name="button_text" placeholder="Watch">
`,

message: `
<label>Message</label>
<textarea name="message"
placeholder="Write your message"></textarea>

<label>Button Text</label>
<input name="button_text" placeholder="Open">

<label>Button URL</label>
<input name="button_url"
placeholder="https://...">
`,

donation: `
<label>Donation Message</label>
<textarea name="donation_message"
placeholder="Support MAYOTUBE"></textarea>

<label>Donation URL</label>
<input name="donation_url"
placeholder="https://...">

<label>Button Text</label>
<input name="button_text" placeholder="Donate">
`,

audio: `
<label>Audio URL</label>
<input name="audio_url"
placeholder="https://...">

<label>Audio Title</label>
<input name="title" placeholder="Audio Title">

<label>Cover Image URL</label>
<input name="cover_url"
placeholder="https://...">
`,

notification: `
<label>Notification Message</label>
<textarea name="notification"
placeholder="Notification text"></textarea>

<label>Button Text</label>
<input name="button_text" placeholder="Open">

<label>Button URL</label>
<input name="button_url"
placeholder="https://...">
`,

image: `
<label>Image URL</label>
<input name="image_url"
placeholder="https://...">

<label>Title</label>
<input name="title" placeholder="Image Title">

<label>Click URL</label>
<input name="click_url"
placeholder="https://...">
`,

video: `
<label>Video URL</label>
<input name="video_url"
placeholder="https://...">

<label>Title</label>
<input name="title" placeholder="Video Title">

<label>Thumbnail URL</label>
<input name="thumbnail_url"
placeholder="https://...">

<label>Description</label>
<textarea name="description"
placeholder="Video Description"></textarea>
`,

gif: `
<label>GIF URL</label>
<input name="gif_url"
placeholder="https://...">

<label>Title</label>
<input name="title" placeholder="GIF Title">

<label>Click URL</label>
<input name="click_url"
placeholder="https://...">
`,

ad: `
<label>Advertisement Image/Media URL</label>
<input name="media_url"
placeholder="https://...">

<label>Advertisement URL</label>
<input name="ad_url"
placeholder="https://...">

<label>Ad Title</label>
<input name="title" placeholder="Advertisement">
`,

music: `
<label>Music URL</label>
<input name="music_url"
placeholder="https://...">

<label>Music Title</label>
<input name="title" placeholder="Music Title">

<label>Artist</label>
<input name="artist" placeholder="Artist Name">
`,

gallery: `
<label>Gallery Video URL</label>
<input name="video_url"
placeholder="https://...">

<label>Title</label>
<input name="title" placeholder="Gallery Video">

<label>Thumbnail URL</label>
<input name="thumbnail_url"
placeholder="https://...">
`,

live: `
<label>Live Channel URL</label>
<input name="live_url"
placeholder="https://...">

<label>Channel Name</label>
<input name="channel_name"
placeholder="Channel Name">

<label>Thumbnail URL</label>
<input name="thumbnail_url"
placeholder="https://...">
`

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
        '<div class="type-info">Selected: ' +
        type.toUpperCase() +
        '</div>' +
        fields[type];
}

</script>

</body>
</html>
"""


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))
