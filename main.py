# ============================================================
# UltraPro FileStore - SINGLE FILE FULL ROOT (PART 1/10)
# Includes: Bot + Web + Admin Panel + Streaming + Rename + Thumbnail
# ============================================================

import os
import re
import json
import base64
import asyncio
import datetime
from typing import List, Tuple, Optional, Dict, Any

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
import aiohttp

# ============================================================
#                       CONFIG
# ============================================================

API_ID = int(os.getenv("API_ID", "27806628"))
API_HASH = os.getenv("API_HASH", "25d88301e886b82826a525b7cf52e090")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8114942266:AAFtInLffruUXodXhf-1bAponngzCI9bRxg")

OWNER_ID = int(os.getenv("OWNER_ID", "8525952693"))

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Bosshub:JMaff0WvazwNxKky@cluster0.l0xcoc1.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "UltraProFileStore")

WEB_URL = os.getenv("WEB_URL", "https://file-store-ultra-pro-bot.onrender.com").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))

# UI / Info
BOT_NAME = os.getenv("BOT_NAME", "UltraPro FileStore")
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "https://t.me/")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "https://t.me/")
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "")

# Logs
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003559364122"))

# Admin
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "UltraProSecretKeyChangeThis")

# ForceSub
FORCE_SUB_ENABLED = os.getenv("FORCE_SUB_ENABLED", "true").lower() == "true"
FSUB_CHANNELS = os.getenv("FSUB_CHANNELS", "")  # "-1001,-1002"

# Shortener
SHORTNER_ENABLED = os.getenv("SHORTNER_ENABLED", "false").lower() == "true"
SHORTNER_API = os.getenv("SHORTNER_API", "")
SHORTNER_API_KEY = os.getenv("SHORTNER_API_KEY", "")

# Stream performance
STREAM_CHUNK_MB = int(os.getenv("STREAM_CHUNK_MB", "1"))
STREAM_CHUNK_SIZE = STREAM_CHUNK_MB * 1024 * 1024

# Security
MAX_BROADCAST_PER_MIN = int(os.getenv("MAX_BROADCAST_PER_MIN", "25"))

# ============================================================
#                   REQUIRED CHECK
# ============================================================

if API_ID == 0 or not API_HASH or not BOT_TOKEN:
    raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN")

if not MONGO_URI:
    raise SystemExit("❌ Missing MONGO_URI")

if not WEB_URL:
    raise SystemExit("❌ Missing WEB_URL")


# ============================================================
#                        DATABASE
# ============================================================

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]

users_col = db["users"]
files_col = db["files"]
bans_col = db["bans"]
fsub_col = db["fsub_channels"]
settings_col = db["settings"]
clones_col = db["clones"]  # ready for future


# ============================================================
#                       BOT INIT
# ============================================================

bot = Client(
    "UltraProSingleFile",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ============================================================
#                    GLOBAL CACHES
# ============================================================

CACHE = {
    "fsub_channels": [],
    "fsub_last": 0,
    "settings": {},
    "settings_last": 0
}


# ============================================================
#                    SMALL UTILITIES
# ============================================================

def now_utc() -> datetime.datetime:
    return datetime.datetime.utcnow()


def humanbytes(size: int) -> str:
    if not size:
        return "0 B"
    power = 1024
    n = 0
    units = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {units[n]}"


def safe_int(x, default=0):
    try:
        return int(x)
    except:
        return default


def b64encode(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def b64decode(code: str) -> str:
    code += "=" * (-len(code) % 4)
    return base64.urlsafe_b64decode(code.encode()).decode()


def get_mime_type(name: str) -> str:
    name = (name or "").lower()
    if name.endswith(".mp4"):
        return "video/mp4"
    if name.endswith(".mkv"):
        return "video/x-matroska"
    if name.endswith(".webm"):
        return "video/webm"
    if name.endswith(".mp3"):
        return "audio/mpeg"
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    return "application/octet-stream"
    # ============================================================
#                    START / HELP COMMAND
# ============================================================

@bot.on_message(filters.private & filters.command(["start"]))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"

    # Add user to DB
    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "joined": now_utc()}},
        upsert=True
    )

    # Force Sub Check
    if FORCE_SUB_ENABLED and FSUB_CHANNELS:
        channels = FSUB_CHANNELS.split(",")
        for ch_id in channels:
            try:
                member = await client.get_chat_member(int(ch_id), user_id)
                if member.status in ["left", "kicked"]:
                    return await message.reply_text(
                        f"❌ You must join our channel to use this bot: {ch_id}"
                    )
            except Exception as e:
                print(f"ForceSub check failed: {e}")

    await message.reply_text(
        f"👋 Hi {message.from_user.first_name}!\n"
        f"🤖 I am {BOT_NAME}\n"
        f"📂 Send me a file to save and share with custom links.\n"
        f"🔗 You can rename files and set thumbnails too!"
    )


# ============================================================
#                 SAVE FILE & AUTO RENAME
# ============================================================

async def save_file(message: Message, new_name: Optional[str] = None, thumb: Optional[str] = None):
    """Saves incoming file, allows rename & thumbnail"""
    file_id = message.document.file_id if message.document else (
        message.video.file_id if message.video else None
    )
    if not file_id:
        return None

    file_name = message.document.file_name if message.document else (
        message.video.file_name if message.video else "unknown_file"
    )

    # Apply rename if provided
    if new_name:
        ext = os.path.splitext(file_name)[1]
        file_name = new_name + ext

    # Generate DB record
    file_record = {
        "file_id": file_id,
        "file_name": file_name,
        "size": message.document.file_size if message.document else message.video.file_size,
        "mime_type": get_mime_type(file_name),
        "user_id": message.from_user.id,
        "thumb": thumb,
        "uploaded": now_utc()
    }

    await files_col.insert_one(file_record)
    return file_record


# ============================================================
#                       THUMBNAIL SUPPORT
# ============================================================

async def get_thumb(user_id: int) -> Optional[str]:
    """Return user's custom thumbnail path if exists"""
    user = await users_col.find_one({"user_id": user_id})
    return user.get("thumb") if user else None


@bot.on_message(filters.private & filters.photo)
async def save_thumbnail(client: Client, message: Message):
    """Save user thumbnail"""
    user_id = message.from_user.id
    file_id = message.photo.file_id

    await users_col.update_one(
        {"user_id": user_id},
        {"$set": {"thumb": file_id}},
        upsert=True
    )
    await message.reply_text("✅ Your custom thumbnail has been saved!")


# ============================================================
#                       FILE HANDLER
# ============================================================

@bot.on_message(filters.private & (filters.document | filters.video))
async def handle_file(client: Client, message: Message):
    user_id = message.from_user.id

    # Check force sub
    if FORCE_SUB_ENABLED and FSUB_CHANNELS:
        channels = FSUB_CHANNELS.split(",")
        for ch_id in channels:
            try:
                member = await client.get_chat_member(int(ch_id), user_id)
                if member.status in ["left", "kicked"]:
                    return await message.reply_text(
                        f"❌ You must join our channel to use this bot: {ch_id}"
                    )
            except Exception as e:
                print(f"ForceSub check failed: {e}")

    # Optional rename
    new_name = None
    if message.caption:
        match = re.search(r"#rename (.+)", message.caption)
        if match:
            new_name = match.group(1).strip()

    thumb = await get_thumb(user_id)

    record = await save_file(message, new_name=new_name, thumb=thumb)
    if not record:
        return await message.reply_text("❌ Failed to save file!")

    # Respond with link
    file_id_encoded = b64encode(str(record["_id"]))
    file_url = f"{WEB_URL}/file/{file_id_encoded}"
    await message.reply_text(f"✅ File saved!\n🔗 Access link: {file_url}")
    # ============================================================
#                  WEB SERVER SETUP (AIOHTTP)
# ============================================================

from aiohttp import web
from bson import ObjectId
from base64 import b64decode

app = web.Application()
routes = web.RouteTableDef()


# ============================================================
#                   FILE DOWNLOAD ROUTE
# ============================================================

@routes.get("/file/{file_id}")
async def download_file(request):
    file_id_encoded = request.match_info["file_id"]
    
    try:
        # Decode ID
        file_id_bytes = b64decode(file_id_encoded)
        file_obj_id = ObjectId(file_id_bytes.decode())
    except Exception:
        return web.Response(text="❌ Invalid file ID", status=400)

    # Fetch from DB
    record = await files_col.find_one({"_id": file_obj_id})
    if not record:
        return web.Response(text="❌ File not found", status=404)

    file_id = record["file_id"]
    file_name = record["file_name"]

    # Generate Telegram download link
    tg_file = await bot.get_file(file_id)
    file_url = tg_file.file_path

    html_content = f"""
    <html>
    <head><title>{file_name}</title></head>
    <body>
        <h3>File: {file_name}</h3>
        <a href="https://api.telegram.org/file/bot{BOT_TOKEN}/{file_url}" download>⬇️ Download</a>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')


# ============================================================
#                   STREAMING / THUMBNAIL SUPPORT
# ============================================================

@routes.get("/stream/{file_id}")
async def stream_file(request):
    file_id_encoded = request.match_info["file_id"]
    
    try:
        file_id_bytes = b64decode(file_id_encoded)
        file_obj_id = ObjectId(file_id_bytes.decode())
    except Exception:
        return web.Response(text="❌ Invalid file ID", status=400)

    record = await files_col.find_one({"_id": file_obj_id})
    if not record:
        return web.Response(text="❌ File not found", status=404)

    file_id = record["file_id"]
    file_name = record["file_name"]

    tg_file = await bot.get_file(file_id)
    file_url = tg_file.file_path

    html_content = f"""
    <html>
    <head><title>{file_name}</title></head>
    <body>
        <h3>Streaming: {file_name}</h3>
        <video width="640" height="480" controls>
            <source src="https://api.telegram.org/file/bot{BOT_TOKEN}/{file_url}" type="{record['mime_type']}">
            Your browser does not support the video tag.
        </video>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')


# ============================================================
#                       RUN WEB SERVER
# ============================================================

app.add_routes(routes)

def run_web():
    web.run_app(app, host="0.0.0.0", port=WEB_PORT) # ============================================================
#                    ADMIN PANEL ROUTES
# ============================================================

from aiohttp import web
from datetime import datetime

# Admin login page
@routes.get("/admin/login")
async def admin_login_page(request):
    body = """
    <h2>🌐 Admin Login</h2>
    <form method="POST" action="/admin/login">
        <label>Username</label><br>
        <input name="username" required><br><br>
        <label>Password</label><br>
        <input name="password" type="password" required><br><br>
        <button type="submit">Login</button>
    </form>
    """
    return web.Response(text=html_page("Admin Login", body), content_type="text/html")


# Admin login POST
@routes.post("/admin/login")
async def admin_login(request):
    data = await request.post()
    username = data.get("username")
    password = data.get("password")

    st = await get_settings(force=True)
    if username == st.get("admin_username") and password == st.get("admin_password"):
        token = make_admin_token(username)
        resp = web.HTTPFound("/admin/dashboard")
        set_cookie(resp, "admin_token", token, days=2)
        return resp

    body = "<h3>❌ Login Failed</h3><a href='/admin/login'>Try Again</a>"
    return web.Response(text=html_page("Login Failed", body), content_type="text/html")


# Admin dashboard
@routes.get("/admin/dashboard")
async def admin_dashboard(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users_count = await users_col.count_documents({})
    files_count = await files_col.count_documents({})
    bans_count = await bans_col.count_documents({})

    body = f"""
    <h2>📊 Admin Dashboard</h2>
    <p>👤 Users: {users_count}</p>
    <p>📁 Files: {files_count}</p>
    <p>🚫 Banned: {bans_count}</p>
    <a href="/admin/users">Manage Users</a> |
    <a href="/admin/files">Manage Files</a> |
    <a href="/admin/logout">Logout</a>
    """
    return web.Response(text=html_page("Dashboard", body), content_type="text/html")


# Admin logout
@routes.get("/admin/logout")
async def admin_logout(request):
    resp = web.HTTPFound("/admin/login")
    resp.del_cookie("admin_token")
    return resp


# ============================================================
#                  MANAGE USERS
# ============================================================

@routes.get("/admin/users")
async def admin_users(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users = []
    async for u in users_col.find({}).sort("joined", -1).limit(50):
        users.append(u)

    body = "<h2>👤 Users (Last 50)</h2><table><tr><th>User ID</th><th>Joined</th><th>Action</th></tr>"
    for u in users:
        uid = u["_id"]
        joined = str(u.get("joined",""))[:19]
        banned = await bans_col.find_one({"_id": uid})
        action = f"<a href='/admin/unban/{uid}'>Unban</a>" if banned else f"<a href='/admin/ban/{uid}'>Ban</a>"
        body += f"<tr><td>{uid}</td><td>{joined}</td><td>{action}</td></tr>"
    body += "</table>"
    return web.Response(text=html_page("Users", body), content_type="text/html")


@routes.get("/admin/ban/{user_id}")
async def admin_ban(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    uid = int(request.match_info["user_id"])
    await ban_user(uid, OWNER_ID)
    raise web.HTTPFound("/admin/users")


@routes.get("/admin/unban/{user_id}")
async def admin_unban(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    uid = int(request.match_info["user_id"])
    await unban_user(uid)
    raise web.HTTPFound("/admin/users")


# ============================================================
#                  MANAGE FILES
# ============================================================

@routes.get("/admin/files")
async def admin_files(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    files = []
    async for f in files_col.find({}).sort("date", -1).limit(50):
        files.append(f)

    body = "<h2>📁 Files (Last 50)</h2><table><tr><th>Name</th><th>Size</th><th>Action</th></tr>"
    for f in files:
        fid = f["_id"]
        name = f.get("name","File")
        size = humanbytes(int(f.get("size",0)))
        body += f"<tr><td>{name}</td><td>{size}</td><td><a href='/admin/file/delete/{fid}'>Delete</a></td></tr>"
    body += "</table>"
    return web.Response(text=html_page("Files", body), content_type="text/html")


@routes.get("/admin/file/delete/{file_id}")
async def admin_file_delete(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    fid = request.match_info["file_id"]
    await files_col.delete_one({"_id": fid})
    raise web.HTTPFound("/admin/files")
    # ============================================================
#                  FORCE SUB & SETTINGS
# ============================================================

# Admin: Update ForceSub channel
@routes.get("/admin/forcesub")
async def admin_forcesub_page(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    st = await get_settings(force=True)
    channel = st.get("force_channel", "Not Set")
    body = f"""
    <h2>📌 ForceSub Channel</h2>
    <p>Current: <b>{channel}</b></p>
    <form method="POST" action="/admin/forcesub">
        <input name="channel" placeholder="Enter channel username or ID" required>
        <button type="submit">Update</button>
    </form>
    <a href="/admin/dashboard">Back to Dashboard</a>
    """
    return web.Response(text=html_page("ForceSub", body), content_type="text/html")


@routes.post("/admin/forcesub")
async def admin_forcesub_update(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    channel = data.get("channel")
    await update_settings({"force_channel": channel})
    body = f"<h3>✅ ForceSub Updated to {channel}</h3><a href='/admin/dashboard'>Dashboard</a>"
    return web.Response(text=html_page("ForceSub Updated", body), content_type="text/html")


# ============================================================
#                   BROADCAST MESSAGE
# ============================================================

@routes.get("/admin/broadcast")
async def admin_broadcast_page(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    body = """
    <h2>📢 Broadcast Message</h2>
    <form method="POST" action="/admin/broadcast">
        <textarea name="message" rows="5" cols="40" placeholder="Enter message to send" required></textarea><br><br>
        <button type="submit">Send Broadcast</button>
    </form>
    <a href="/admin/dashboard">Back to Dashboard</a>
    """
    return web.Response(text=html_page("Broadcast", body), content_type="text/html")


@routes.post("/admin/broadcast")
async def admin_broadcast_send(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    msg = data.get("message")
    users = users_col.find({})
    sent_count = 0

    async for u in users:
        try:
            await bot.send_message(u["_id"], msg)
            sent_count += 1
        except:
            continue

    body = f"<h3>✅ Broadcast Sent to {sent_count} users</h3><a href='/admin/dashboard'>Back to Dashboard</a>"
    return web.Response(text=html_page("Broadcast Sent", body), content_type="text/html")


# ============================================================
#                   TOGGLE SHORTENER
# ============================================================

@routes.get("/admin/shortener")
async def admin_shortener_page(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    st = await get_settings(force=True)
    enabled = st.get("shortener_enabled", False)
    status = "Enabled ✅" if enabled else "Disabled ❌"

    body = f"""
    <h2>🔗 URL Shortener</h2>
    <p>Status: <b>{status}</b></p>
    <form method="POST" action="/admin/shortener">
        <button type="submit">Toggle</button>
    </form>
    <a href="/admin/dashboard">Back to Dashboard</a>
    """
    return web.Response(text=html_page("Shortener", body), content_type="text/html")


@routes.post("/admin/shortener")
async def admin_shortener_toggle(request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    st = await get_settings(force=True)
    current = st.get("shortener_enabled", False)
    await update_settings({"shortener_enabled": not current})

    new_status = "Enabled ✅" if not current else "Disabled ❌"
    body = f"<h3>🔄 URL Shortener {new_status}</h3><a href='/admin/dashboard'>Dashboard</a>"
    return web.Response(text=html_page("Shortener Toggled", body), content_type="text/html")
    # ============================================================
#                  FILE UPLOAD & AUTO-RENAME
# ============================================================

UPLOAD_FOLDER = "./uploads"
THUMB_FOLDER = "./thumbnails"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

# Allowed file types
ALLOWED_EXTENSIONS = {"mp4", "mkv", "jpg", "png", "txt", "pdf", "zip"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_name(filename):
    # Auto rename: original name + timestamp
    ext = filename.rsplit(".", 1)[1] if "." in filename else ""
    name = filename.rsplit(".", 1)[0]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{name}_{timestamp}.{ext}" if ext else f"{name}_{timestamp}"


# Upload page
@routes.get("/upload")
async def upload_page(request):
    body = """
    <h2>📤 Upload File</h2>
    <form action="/upload" method="POST" enctype="multipart/form-data">
        <input type="file" name="file" required><br><br>
        <label>Thumbnail (optional)</label><br>
        <input type="file" name="thumb"><br><br>
        <button type="submit">Upload</button>
    </form>
    <a href="/">Home</a>
    """
    return web.Response(text=html_page("Upload File", body), content_type="text/html")


# Handle file upload
@routes.post("/upload")
async def handle_upload(request):
    reader = await request.multipart()
    field = await reader.next()
    if field.name != "file":
        return web.Response(text="❌ No file provided", content_type="text/html")

    filename = field.filename
    if not allowed_file(filename):
        return web.Response(text="❌ File type not allowed", content_type="text/html")

    new_name = generate_unique_name(filename)
    save_path = os.path.join(UPLOAD_FOLDER, new_name)

    # Save uploaded file
    with open(save_path, "wb") as f:
        while True:
            chunk = await field.read_chunk()  # 8192 bytes default
            if not chunk:
                break
            f.write(chunk)

    # Handle optional thumbnail
    thumb_field = await reader.next()
    thumb_path = None
    if thumb_field and thumb_field.name == "thumb" and thumb_field.filename:
        thumb_name = generate_unique_name(thumb_field.filename)
        thumb_path = os.path.join(THUMB_FOLDER, thumb_name)
        with open(thumb_path, "wb") as f:
            while True:
                chunk = await thumb_field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)

    body = f"""
    <h3>✅ File Uploaded Successfully</h3>
    <p>Filename: <b>{new_name}</b></p>
    <p>Thumbnail: <b>{os.path.basename(thumb_path) if thumb_path else 'None'}</b></p>
    <a href="/upload">Upload Another</a> | <a href="/">Home</a>
    """
    return web.Response(text=html_page("Upload Success", body), content_type="text/html")
    # ============================================================
#                  TELEGRAM SEND FILES + THUMBNAILS
# ============================================================

from pyrogram.types import InputMediaPhoto, InputMediaDocument

async def send_uploaded_file(client: Client, chat_id: int, file_path: str, thumb_path: str = None):
    """
    Sends a file to a Telegram user using Pyrogram bot.
    Supports optional thumbnail for videos/photos/documents.
    """
    try:
        ext = file_path.rsplit(".", 1)[1].lower() if "." in file_path else ""
        if ext in ["jpg", "jpeg", "png"]:
            # Send as photo
            await client.send_photo(
                chat_id,
                photo=file_path,
                caption=f"📁 File: {os.path.basename(file_path)}"
            )
        else:
            # Send as document/video/audio
            kwargs = {"caption": f"📁 File: {os.path.basename(file_path)}"}
            if thumb_path and os.path.exists(thumb_path):
                kwargs["thumb"] = thumb_path

            await client.send_document(
                chat_id,
                document=file_path,
                **kwargs
            )
    except Exception as e:
        print(f"❌ Error sending file: {e}")
        return False
    return True


# Example route to send uploaded file to bot user
@routes.get("/send/{filename}/{user_id}")
async def route_send_file(request):
    filename = request.match_info["filename"]
    user_id = safe_int(request.match_info["user_id"])
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(file_path):
        return web.Response(text="❌ File not found", status=404)

    # Check if thumbnail exists
    thumb_path = None
    thumb_candidate = os.path.join(THUMB_FOLDER, filename)
    if os.path.exists(thumb_candidate):
        thumb_path = thumb_candidate

    success = await send_uploaded_file(bot, user_id, file_path, thumb_path)
    body = "<h2>✅ File sent successfully!</h2>" if success else "<h2>❌ Failed to send file!</h2>"
    body += '<a href="/">Home</a>'
    return web.Response(text=html_page("Send File", body), content_type="text/html")
    # ============================================================
#                SHORT LINKS + WEB STREAM
# ============================================================

async def get_short_url(url: str) -> str:
    """
    Returns a short URL if shortener is enabled.
    Otherwise, returns original URL.
    """
    st = await get_settings()
    if not st.get("shortner_enabled", False):
        return url

    if not SHORTNER_API or not SHORTNER_API_KEY:
        return url

    api_url = f"{SHORTNER_API}?api={SHORTNER_API_KEY}&url={url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=15) as resp:
                data = await resp.json(content_type=None)
                for k in ("shortenedUrl", "short", "short_url", "result_url", "url"):
                    if k in data and data[k]:
                        return data[k]
    except:
        return url
    return url


async def generate_file_links(file_unique_id: str) -> dict:
    """
    Generates Bot Link, Watch Link, and Direct Download Link
    for a given file.
    """
    bot_link = make_bot_link(bot.me.username, b64e(file_unique_id))
    watch_link = make_watch_url(file_unique_id)
    dl_link = make_dl_url(file_unique_id)

    # Apply URL shortener if enabled
    bot_link = await get_short_url(bot_link)
    watch_link = await get_short_url(watch_link)
    dl_link = await get_short_url(dl_link)

    return {
        "bot": bot_link,
        "watch": watch_link,
        "download": dl_link
    }


# Example usage when user uploads a file
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def upload_file_handler(client: Client, message: Message):
    await add_user(message.from_user.id)
    
    if await is_banned(message.from_user.id):
        return await message.reply_text("🚫 You are banned!")

    media = message.document or message.video or message.audio or message.photo
    if not media:
        return

    file_unique_id = media.file_unique_id
    file_name = getattr(media, "file_name", None) or "File"
    file_size = getattr(media, "file_size", 0) or 0
    tg_file_id = media.file_id

    # Save file in DB
    await save_file_to_db(file_unique_id, tg_file_id, file_name, file_size, message.from_user.id)

    links = await generate_file_links(file_unique_id)
    text = (
        f"✅ **File Stored Successfully!**\n\n"
        f"📁 **Name:** `{file_name}`\n"
        f"📦 **Size:** `{humanbytes(file_size)}`\n\n"
        "🔗 **Share Links:**\n"
        f"🤖 Bot: `{links['bot']}`\n"
        f"🎬 Watch: `{links['watch']}`\n"
        f"⬇️ Download: `{links['download']}`\n"
    )

    buttons = [
        [InlineKeyboardButton("🤖 Bot Link", url=links["bot"])],
        [InlineKeyboardButton("🎬 Watch / Stream", url=links["watch"])],
        [InlineKeyboardButton("⬇️ Download", url=links["download"])],
    ]

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
    # ============================================================
#                FORCE SUBSCRIBE CHECK
# ============================================================

async def get_all_fsub_channels(force: bool = False) -> list:
    """
    Returns unique list of FSub channels from ENV + DB.
    Caches results for performance.
    """
    t = int(datetime.datetime.utcnow().timestamp())
    if not force and CACHE.get("fsub_channels") and (t - CACHE["fsub_last"] < 20):
        return CACHE["fsub_channels"]

    channels = []

    # ENV channels
    if FSUB_CHANNELS.strip():
        for c in FSUB_CHANNELS.split(","):
            c = c.strip()
            if c:
                try:
                    channels.append(int(c))
                except:
                    pass

    # DB channels
    async for doc in fsub_col.find({}):
        try:
            channels.append(int(doc["_id"]))
        except:
            pass

    # Remove duplicates
    channels = list(dict.fromkeys(channels))

    CACHE["fsub_channels"] = channels
    CACHE["fsub_last"] = t
    return channels


async def force_sub_check(client: Client, user_id: int) -> tuple:
    """
    Checks if a user has joined all FSub channels.
    Returns (ok: bool, message: str, buttons: list)
    """
    st = await get_settings()
    if not st.get("force_sub_enabled", True):
        return True, "", []

    channels = await get_all_fsub_channels()
    if not channels:
        return True, "", []

    buttons = []
    missing = 0

    for ch in channels:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                missing += 1
                chat = await client.get_chat(ch)
                invite = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                if invite:
                    buttons.append([InlineKeyboardButton(f"📢 Join {chat.title}", url=invite)])
        except:
            # count as missing if cannot get member
            missing += 1

    if missing > 0:
        return False, "🔒 You must join all channels to use this bot.", buttons

    return True, "", []


# ============================================================
#               FORCE SUB IN /start COMMAND
# ============================================================

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await add_user(message.from_user.id)

    if await is_banned(message.from_user.id):
        return await message.reply_text("🚫 You are banned from using this bot.")

    ok, fmsg, btns = await force_sub_check(client, message.from_user.id)
    if not ok:
        btns.append([InlineKeyboardButton("🔁 Try Again", url=f"https://t.me/{client.me.username}?start=checksub")])
        return await message.reply_text(fmsg, reply_markup=InlineKeyboardMarkup(btns), disable_web_page_preview=True)

    st = await get_settings()
    buttons = [
        [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("🎬 Web Stream", url=WEB_URL), InlineKeyboardButton("🌐 Admin Panel", url=f"{WEB_URL}/admin/login")],
        [InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL), InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)]
    ]

    text = (
        f"👋 **Welcome to {st.get('site_name', BOT_NAME)}!**\n\n"
        "📌 Send me any file and I will store it.\n\n"
        "You will get:\n"
        "✅ Shareable bot link\n"
        "✅ Web stream link\n"
        "✅ Direct download link\n\n"
        "Send file now 📁"
    )

    if START_IMAGE_URL:
        return await message.reply_photo(START_IMAGE_URL, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    # ============================================================
#                  ADMIN PANEL (WEB) SETUP
# ============================================================

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import secrets
import os

# ------------------------------------------------------------
# FastAPI App & Templates
# ------------------------------------------------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=ADMIN_SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------
def is_logged_in(request: Request):
    return request.session.get("admin_logged_in", False)

def login_required(func):
    async def wrapper(request: Request, *args, **kwargs):
        if not is_logged_in(request):
            return RedirectResponse("/admin/login")
        return await func(request, *args, **kwargs)
    return wrapper

async def save_settings_to_db(settings: dict):
    await settings_col.update_one({"_id": 1}, {"$set": settings}, upsert=True)

async def load_settings_from_db() -> dict:
    doc = await settings_col.find_one({"_id": 1})
    if not doc:
        return {}
    return doc

# ------------------------------------------------------------
# Admin Login
# ------------------------------------------------------------
@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})

@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["admin_logged_in"] = True
        return RedirectResponse("/admin/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login")

# ------------------------------------------------------------
# Admin Dashboard
# ------------------------------------------------------------
@app.get("/admin/dashboard", response_class=HTMLResponse)
@login_required
async def admin_dashboard(request: Request):
    settings = await load_settings_from_db()
    users_count = await users_col.count_documents({})
    files_count = await files_col.count_documents({})
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "settings": settings,
            "users_count": users_count,
            "files_count": files_count
        }
    )

# ------------------------------------------------------------
# Update Settings
# ------------------------------------------------------------
@app.post("/admin/settings/update", response_class=RedirectResponse)
@login_required
async def update_settings(request: Request,
                          site_name: str = Form(...),
                          force_sub_enabled: str = Form(...),
                          max_file_size: str = Form(...)):
    new_settings = {
        "site_name": site_name,
        "force_sub_enabled": True if force_sub_enabled == "on" else False,
        "max_file_size": int(max_file_size),
    }
    await save_settings_to_db(new_settings)
    return RedirectResponse("/admin/dashboard", status_code=302)

# ------------------------------------------------------------
# File Management
# ------------------------------------------------------------
@app.get("/admin/files", response_class=HTMLResponse)
@login_required
async def admin_files(request: Request):
    files = await files_col.find().to_list(100)
    return templates.TemplateResponse("files.html", {"request": request, "files": files})

@app.get("/admin/files/delete/{file_id}")
@login_required
async def admin_delete_file(request: Request, file_id: str):
    await files_col.delete_one({"_id": file_id})
    # optionally delete from disk if stored locally
    return RedirectResponse("/admin/files", status_code=302)

# ------------------------------------------------------------
# Users Management
# ------------------------------------------------------------
@app.get("/admin/users", response_class=HTMLResponse)
@login_required
async def admin_users(request: Request):
    users = await users_col.find().to_list(100)
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.get("/admin/users/ban/{user_id}")
@login_required
async def admin_ban_user(request: Request, user_id: int):
    await banned_col.update_one({"_id": user_id}, {"$set": {"banned": True}}, upsert=True)
    return RedirectResponse("/admin/users", status_code=302)

@app.get("/admin/users/unban/{user_id}")
@login_required
async def admin_unban_user(request: Request, user_id: int):
    await banned_col.delete_one({"_id": user_id})
    return RedirectResponse("/admin/users", status_code=302)

# ------------------------------------------------------------
# FSub Channel Management
# ------------------------------------------------------------
@app.get("/admin/fsub", response_class=HTMLResponse)
@login_required
async def admin_fsub(request: Request):
    channels = await fsub_col.find().to_list(50)
    return templates.TemplateResponse("fsub.html", {"request": request, "channels": channels})

@app.post("/admin/fsub/add")
@login_required
async def add_fsub_channel(request: Request, channel_id: int = Form(...)):
    await fsub_col.update_one({"_id": channel_id}, {"$set": {}}, upsert=True)
    return RedirectResponse("/admin/fsub", status_code=302)

@app.get("/admin/fsub/remove/{channel_id}")
@login_required
async def remove_fsub_channel(request: Request, channel_id: int):
    await fsub_col.delete_one({"_id": channel_id})
    return RedirectResponse("/admin/fsub", status_code=302)
    # ============================================================
#                  FILE UPLOAD & AUTO-RENAME
# ============================================================

from fastapi import UploadFile, File
from PIL import Image
import aiofiles
import uuid
import shutil

# ------------------------------------------------------------
# Helper: Generate Unique Filename
# ------------------------------------------------------------
def generate_unique_filename(original_name: str) -> str:
    ext = os.path.splitext(original_name)[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return unique_name

# ------------------------------------------------------------
# Helper: Generate Thumbnail for Images
# ------------------------------------------------------------
def generate_thumbnail(image_path: str, thumb_path: str, size=(200, 200)):
    try:
        img = Image.open(image_path)
        img.thumbnail(size)
        img.save(thumb_path)
    except Exception as e:
        print(f"Thumbnail generation failed: {e}")

# ------------------------------------------------------------
# Upload Endpoint
# ------------------------------------------------------------
@app.post("/upload-file")
@login_required
async def upload_file(request: Request, file: UploadFile = File(...)):
    # Check file size limit
    contents = await file.read()
    if len(contents) > settings.get("max_file_size", 20 * 1024 * 1024):
        return HTMLResponse("File too large", status_code=400)

    # Auto-rename file
    saved_name = generate_unique_filename(file.filename)
    saved_path = os.path.join("uploads", saved_name)

    # Save file
    async with aiofiles.open(saved_path, 'wb') as out_file:
        await out_file.write(contents)

    # Generate thumbnail if image
    if file.content_type.startswith("image/"):
        thumb_name = f"thumb_{saved_name}"
        thumb_path = os.path.join("uploads", thumb_name)
        generate_thumbnail(saved_path, thumb_path)

    # Save file info to DB
    await files_col.insert_one({
        "_id": saved_name,
        "original_name": file.filename,
        "saved_name": saved_name,
        "user_id": request.session.get("user_id", 0),
        "thumbnail": thumb_name if file.content_type.startswith("image/") else None,
        "size": len(contents)
    })

    return HTMLResponse(f"File uploaded successfully: {saved_name}")

# ------------------------------------------------------------
# Download Endpoint
# ------------------------------------------------------------
@app.get("/download/{file_id}")
async def download_file(file_id: str):
    file_doc = await files_col.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = os.path.join("uploads", file_doc["saved_name"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(file_path, filename=file_doc["original_name"])

# ------------------------------------------------------------
# Rename Endpoint
# ------------------------------------------------------------
@app.post("/admin/files/rename/{file_id}")
@login_required
async def rename_file(file_id: str, new_name: str = Form(...)):
    file_doc = await files_col.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    old_path = os.path.join("uploads", file_doc["saved_name"])
    new_ext = os.path.splitext(file_doc["saved_name"])[1]
    new_saved_name = f"{new_name}{new_ext}"
    new_path = os.path.join("uploads", new_saved_name)

    # Rename file
    shutil.move(old_path, new_path)

    # Update DB
    await files_col.update_one({"_id": file_id}, {"$set": {"saved_name": new_saved_name}})

    return RedirectResponse("/admin/files", status_code=302)

# ------------------------------------------------------------
# Thumbnail Download Endpoint
# ------------------------------------------------------------
@app.get("/thumbnail/{file_id}")
async def get_thumbnail(file_id: str):
    file_doc = await files_col.find_one({"_id": file_id})
    if not file_doc or not file_doc.get("thumbnail"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    thumb_path = os.path.join("uploads", file_doc["thumbnail"])
    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail missing")
    return FileResponse(thumb_path, filename=file_doc["thumbnail"])
    # ============================================================
#                TELEGRAM BOT FILE HANDLER
# ============================================================

from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.utils import executor

# Initialize bot
bot = Bot(token=settings.get("telegram_bot_token"))
dp = Dispatcher(bot)

# ------------------------------------------------------------
# Handle document uploads
# ------------------------------------------------------------
@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: types.Message):
    document = message.document

    # Download file
    file_info = await bot.get_file(document.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    # Auto-rename
    saved_name = generate_unique_filename(document.file_name)
    saved_path = os.path.join("uploads", saved_name)

    with open(saved_path, "wb") as f:
        f.write(downloaded_file.read())

    # Save to DB
    await files_col.insert_one({
        "_id": saved_name,
        "original_name": document.file_name,
        "saved_name": saved_name,
        "user_id": message.from_user.id,
        "size": document.file_size,
        "thumbnail": None
    })

    await message.reply(f"File uploaded and renamed: {saved_name}")

# ------------------------------------------------------------
# Handle photo uploads
# ------------------------------------------------------------
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]  # highest resolution

    # Download file
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    # Auto-rename
    saved_name = generate_unique_filename("photo.jpg")
    saved_path = os.path.join("uploads", saved_name)

    with open(saved_path, "wb") as f:
        f.write(downloaded_file.read())

    # Generate thumbnail
    thumb_name = f"thumb_{saved_name}"
    thumb_path = os.path.join("uploads", thumb_name)
    generate_thumbnail(saved_path, thumb_path)

    # Save to DB
    await files_col.insert_one({
        "_id": saved_name,
        "original_name": "photo.jpg",
        "saved_name": saved_name,
        "user_id": message.from_user.id,
        "size": os.path.getsize(saved_path),
        "thumbnail": thumb_name
    })

    await message.reply(f"Photo uploaded successfully: {saved_name}")

# ------------------------------------------------------------
# Send file back to user
# ------------------------------------------------------------
@dp.message_handler(commands=["getfile"])
async def send_file(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: /getfile <file_id>")
        return

    file_id = args[1]
    file_doc = await files_col.find_one({"_id": file_id})
    if not file_doc:
        await message.reply("File not found!")
        return

    file_path = os.path.join("uploads", file_doc["saved_name"])
    await message.reply_document(InputFile(file_path, filename=file_doc["original_name"]))

# ------------------------------------------------------------
# Start bot
# ------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling()
# ============================================================
# RUN BOT + WEB
# ============================================================

async def run_all():
    await bot.start()
    me = await bot.get_me()
    print("🤖 Bot Started:", me.username)

    app = build_web_app()  # call function to build web panel routes
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("🌐 Web Started on PORT:", PORT)
    print("🌐 WEB_URL:", WEB_URL)

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(run_all())
