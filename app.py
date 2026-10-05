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
        <title>MAYOTUBE Admin Login</title>
        <style>
            body{
                margin:0;
                min-height:100vh;
                display:flex;
                align-items:center;
                justify-content:center;
                background:#111;
                color:#fff;
                font-family:Arial,sans-serif;
            }
            .box{
                width:90%;
                max-width:400px;
                padding:25px;
                box-sizing:border-box;
                background:#1d1d1d;
                border-radius:16px;
            }
            h2{
                text-align:center;
                margin-top:0;
            }
            input{
                width:100%;
                padding:14px;
                margin:12px 0;
                box-sizing:border-box;
                border:0;
                border-radius:8px;
                background:#333;
                color:#fff;
            }
            button{
                width:100%;
                padding:14px;
                border:0;
                border-radius:8px;
                background:#fff;
                color:#111;
                font-weight:bold;
                cursor:pointer;
            }
            p{
                text-align:center;
                color:#aaa;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>MAYOTUBE ADMIN</h2>
            <p>Owner Only</p>
            <form method="post" action="/admin/login">
                <input
                    type="password"
                    name="token"
                    placeholder="Admin Token"
                    required
                    autocomplete="off">
                <button type="submit">LOGIN</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.post("/admin/login")
def admin_login_submit():
    if not ADMIN_TOKEN:
        return "Admin security is not configured.", 500

    token = request.form.get("token", "")

    if not hmac.compare_digest(token, ADMIN_TOKEN):
        return """
        <html>
        <body style="background:#111;color:white;font-family:Arial;text-align:center;padding:50px">
            <h2>Login Failed</h2>
            <p>Invalid Admin Token.</p>
            <a href="/admin" style="color:white">Try Again</a>
        </body>
        </html>
        """, 401

    session.clear()
    session["admin"] = True
    return redirect(url_for("admin_dashboard"))


@app.get("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>MAYOTUBE Admin</title>
        <style>
            body{
                margin:0;
                background:#111;
                color:#fff;
                font-family:Arial,sans-serif;
                padding:25px;
            }
            .box{
                max-width:700px;
                margin:auto;
                background:#1d1d1d;
                padding:25px;
                border-radius:16px;
            }
            a{
                display:inline-block;
                margin-top:20px;
                padding:12px 18px;
                background:#fff;
                color:#111;
                text-decoration:none;
                border-radius:8px;
                font-weight:bold;
            }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>MAYOTUBE ADMIN</h1>
            <p>Owner Admin Login Successful ✅</p>
            <p>Admin Dashboard will be added in the next step.</p>
            <a href="/admin/logout">Logout</a>
        </div>
    </body>
    </html>
    """


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))
