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
            body{font-family:Arial;background:#f2f2f2;margin:0;padding:30px}
            .box{max-width:420px;margin:50px auto;background:white;padding:25px;
                 border-radius:14px;box-shadow:0 4px 15px #bbb}
            h2{text-align:center}
            input,button{width:100%;padding:13px;margin-top:12px;
                         box-sizing:border-box;border-radius:8px}
            input{border:1px solid #ccc}
            button{border:0;background:#111;color:white;font-size:16px}
            .error{color:red;text-align:center}
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
    <h3 style="text-align:center;color:red">
        Invalid Admin Token
    </h3>
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
            body{font-family:Arial;background:#f2f2f2;margin:0;padding:15px}
            .box{max-width:700px;margin:auto}
            .header{background:#111;color:white;padding:20px;border-radius:14px;
                    margin-bottom:15px}
            .card{background:white;padding:20px;margin-bottom:12px;
                  border-radius:14px;box-shadow:0 2px 8px #ccc}
            h2,h3{margin-top:0}
            .status{color:green;font-weight:bold}
            .btn{display:block;text-decoration:none;background:#111;color:white;
                 text-align:center;padding:12px;border-radius:8px;margin-top:10px}
        </style>
    </head>
    <body>
        <div class="box">

            <div class="header">
                <h2>MAYOTUBE ADMIN</h2>
                <div class="status">Owner Admin ✓</div>
            </div>

            <div class="card">
                <h3>Homepage Content</h3>
                <p>یہاں سے MAYOTUBE Homepage کا Content manage کیا جائے گا۔</p>
            </div>

            <div class="card">
                <h3>Content Management</h3>
                <p>Text, Image, Video, GIF, Notification, Ads, Music,
                Gallery اور Live Channel کے tools اگلے مراحل میں شامل ہوں گے۔</p>
            </div>

            <div class="card">
                <h3>System Status</h3>
                <p class="status">Backend Online ✓</p>
                <p class="status">Admin Authenticated ✓</p>
            </div>

            <a class="btn" href="/admin/logout">Logout</a>

        </div>
    </body>
    </html>
    """


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))
