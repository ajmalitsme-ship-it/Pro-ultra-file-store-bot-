# ============================================================
# UltraPro FileStore - SINGLE FILE FULL ROOT (MAIN.PY PART 1)
# Includes:
#  - File Store + Share Links
#  - Web Stream + Range Support
#  - Shortener
#  - Multi ForceSub (ENV + DB)
#  - Users DB + Files DB
#  - Admin Login System
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
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "https://radare.arzfun.com/api/tg/photo?id=AgACAgQAAxkBAAEL61Bplx4lS79xzA_Aw0u96UpcyLOd_gAC3A1rG0H75VPNP_NHb-SW5wEAAwIAA3gAAzoE")

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


def b64e(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def b64d(code: str) -> str:
    code += "=" * (-len(code) % 4)
    return base64.urlsafe_b64decode(code.encode()).decode()


def safe_int(x, default=0):
    try:
        return int(x)
    except:
        return default


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


def make_bot_link(username: str, code: str) -> str:
    return f"https://t.me/{username}?start={code}"


def make_watch_url(file_id: str) -> str:
    return f"{WEB_URL}/watch/{file_id}"


def make_dl_url(file_id: str) -> str:
    return f"{WEB_URL}/dl/{file_id}"

# ============================================================
#                  DATABASE HELPERS
# ============================================================

async def add_user(user_id: int):
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"_id": user_id, "joined": now_utc()}},
        upsert=True
    )


async def is_banned(user_id: int) -> bool:
    return bool(await bans_col.find_one({"_id": user_id}))


async def ban_user(user_id: int, by: int):
    await bans_col.update_one(
        {"_id": user_id},
        {"$set": {"_id": user_id, "by": by, "date": now_utc()}},
        upsert=True
    )


async def unban_user(user_id: int):
    await bans_col.delete_one({"_id": user_id})


async def save_file_to_db(file_unique_id: str, tg_file_id: str, name: str, size: int, from_user: int):
    await files_col.update_one(
        {"_id": file_unique_id},
        {"$set": {
            "_id": file_unique_id,
            "tg_file_id": tg_file_id,
            "name": name,
            "size": int(size or 0),
            "mime": get_mime_type(name),
            "from_user": from_user,
            "date": now_utc()
        }},
        upsert=True
)
  # ============================================================
#                     BOT COMMANDS / CALLBACKS
# ============================================================

@bot.on_message(filters.command("start") & ~filters.edited)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)

    text = f"👋 Hi {message.from_user.first_name}!\n\n" \
           f"Welcome to **{BOT_NAME}**.\n" \
           f"Send me any file and I will store it for you.\n\n" \
           f"📌 Support: [Click Here]({SUPPORT_GROUP})\n" \
           f"📢 Updates: [Click Here]({UPDATES_CHANNEL})"

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Open Web", url=WEB_URL)],
        [InlineKeyboardButton("🔗 Support", url=SUPPORT_GROUP),
         InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL)]
    ])

    await message.reply_photo(
        photo=START_IMAGE_URL,
        caption=text,
        reply_markup=buttons
    )


# ============================================================
#                     FILE HANDLER
# ============================================================

@bot.on_message(
    filters.document | filters.video | filters.audio | filters.photo
)
async def handle_file(client: Client, message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        return await message.reply_text("❌ You are banned from using this bot.")

    file = message.document or message.video or message.audio
    name = getattr(file, "file_name", "file")
    size = getattr(file, "file_size", 0)
    file_id = file.file_id

    # Generate unique ID based on Telegram file_unique_id
    unique_id = getattr(file, "file_unique_id", None)
    if not unique_id:
        unique_id = b64e(f"{file_id}_{now_utc().timestamp()}")

    await save_file_to_db(unique_id, file_id, name, size, user_id)

    watch_link = make_watch_url(unique_id)
    dl_link = make_dl_url(unique_id)

    text = f"✅ **File Saved!**\n\n" \
           f"**Name:** {name}\n" \
           f"**Size:** {humanbytes(size)}\n\n" \
           f"🔗 [Watch Online]({watch_link})\n" \
           f"⬇️ [Download]({dl_link})"

    await message.reply_text(text, disable_web_page_preview=False)


# ============================================================
#                     CALLBACK HANDLERS
# ============================================================

@bot.on_callback_query()
async def handle_callbacks(client: Client, query: CallbackQuery):
    data = query.data

    if data.startswith("ban_"):
        if query.from_user.id != OWNER_ID:
            return await query.answer("❌ Only owner can use this.", show_alert=True)
        target_id = int(data.split("_")[1])
        await ban_user(target_id, OWNER_ID)
        await query.answer("✅ User banned successfully.")
        await query.message.edit_text(f"User {target_id} has been banned.")

    elif data.startswith("unban_"):
        if query.from_user.id != OWNER_ID:
            return await query.answer("❌ Only owner can use this.", show_alert=True)
        target_id = int(data.split("_")[1])
        await unban_user(target_id)
        await query.answer("✅ User unbanned successfully.")
        await query.message.edit_text(f"User {target_id} has been unbanned.")


# ============================================================
#                     OWNER COMMANDS
# ============================================================

@bot.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats_cmd(client: Client, message: Message):
    total_users = await users_col.count_documents({})
    total_files = await files_col.count_documents({})
    total_banned = await bans_col.count_documents({})

    text = f"📊 **Bot Statistics**\n\n" \
           f"👤 Total Users: {total_users}\n" \
           f"📁 Total Files: {total_files}\n" \
           f"⛔ Banned Users: {total_banned}"

    await message.reply_text(text)


@bot.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /broadcast <message>")

    bc_msg = message.text.split(" ", 1)[1]
    users_cursor = users_col.find({})
    count = 0
    async for user in users_cursor:
        try:
            await client.send_message(user["_id"], bc_msg)
            count += 1
            await asyncio.sleep(0.05)  # slight delay to avoid flood
        except:
            pass

    await message.reply_text(f"✅ Broadcast sent to {count} users.")


@bot.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /ban <user_id>")
    target_id = int(message.command[1])
    await ban_user(target_id, OWNER_ID)
    await message.reply_text(f"✅ User {target_id} banned.")


@bot.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /unban <user_id>")
    target_id = int(message.command[1])
    await unban_user(target_id)
    await message.reply_text(f"✅ User {target_id} unbanned.")
  # ============================================================
#                     WEB SERVER HELPERS
# ============================================================

def html_page(title: str, body: str) -> str:
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: Arial,sans-serif; background:#0b0b0f; color:#fff; margin:0; padding:0; }}
.wrap {{ max-width:980px; margin:auto; padding:18px; }}
.card {{ background:#141421; border-radius:16px; padding:18px; margin-top:14px; }}
a {{ color:#7aa7ff; text-decoration:none; }}
.btn {{ display:inline-block; padding:10px 14px; border-radius:12px; background:rgba(255,255,255,0.06); margin:4px 0; }}
table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
th, td {{ padding:10px; border-bottom:1px solid rgba(255,255,255,0.08); font-size:14px; text-align:left; }}
th {{ background: rgba(255,255,255,0.06); }}
.muted {{ opacity:0.75; }}
</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>
"""


def set_cookie(resp: web.Response, key: str, value: str, days: int = 1):
    max_age = days * 24 * 60 * 60
    resp.set_cookie(key, value, max_age=max_age, httponly=True, samesite="Lax")


def get_cookie(request: web.Request, key: str) -> str:
    return request.cookies.get(key, "")


def make_admin_token(username: str) -> str:
    raw = f"{username}|{SECRET_KEY}|{int(datetime.datetime.utcnow().timestamp())}"
    return b64e(raw)


def verify_admin_token(token: str) -> bool:
    try:
        raw = b64d(token)
        parts = raw.split("|")
        if len(parts) < 3:
            return False
        if parts[1] != SECRET_KEY:
            return False
        return True
    except:
        return False


async def require_admin(request: web.Request) -> bool:
    token = get_cookie(request, "admin_token")
    return verify_admin_token(token)


# ============================================================
#                     WEB ROUTES
# ============================================================

async def route_home(request: web.Request):
    body = f"""
    <h2>🎬 {BOT_NAME} - Web Stream</h2>
    <div class="card">
      <p class="muted">
        This server provides streaming & direct download for Telegram files.
      </p>
      <a class="btn" href="/admin/login">🌐 Admin Panel</a>
      <a class="btn" href="{SUPPORT_GROUP}">💬 Support</a>
    </div>
    """
    return web.Response(text=html_page("Home", body), content_type="text/html")


async def route_watch(request: web.Request):
    file_id = request.match_info["file_id"].strip()
    data = await files_col.find_one({"_id": file_id})
    if not data:
        return web.Response(text="File not found!", status=404)

    name = data.get("name", "Video")
    dl = make_dl_url(file_id)
    mime = data.get("mime", "video/mp4")

    body = f"""
    <h2>🎬 {name}</h2>
    <div class="card">
      <video width="100%" controls playsinline>
        <source src="{dl}" type="{mime}">
      </video>
      <br><br>
      <a class="btn" href="{dl}">⬇️ Direct Download</a>
    </div>
    """
    return web.Response(text=html_page(name, body), content_type="text/html")


# ============================================================
#             STREAM / DOWNLOAD WITH RANGE SUPPORT
# ============================================================

async def route_download(request: web.Request):
    file_id = request.match_info["file_id"].strip()
    data = await files_col.find_one({"_id": file_id})
    if not data:
        return web.Response(text="File not found!", status=404)

    tg_file_id = data["tg_file_id"]
    file_name = data.get("name", "file.bin")
    mime = data.get("mime", "application/octet-stream")
    size = int(data.get("size", 0))

    range_header = request.headers.get("Range")
    start = 0
    end = size - 1

    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))
            else:
                end = size - 1

    length = end - start + 1
    headers = {
        "Content-Type": mime,
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Cache-Control": "no-store",
    }
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    status = 206 if range_header else 200
    resp = web.StreamResponse(status=status, headers=headers)
    await resp.prepare(request)

    try:
        async for chunk in bot.stream_media(
            message=None,
            file_id=tg_file_id,
            offset=start,
            limit=length
        ):
            await resp.write(chunk)
    except Exception as e:
        return web.Response(text=f"Stream error: {e}", status=500)

    await resp.write_eof()
    return resp
    # ============================================================
#                 WEB: ADMIN LOGIN PAGE
# ============================================================

async def route_admin_login(request: web.Request):
    if await require_admin(request):
        raise web.HTTPFound("/admin/dashboard")

    body = f"""
    <h2>🌐 {BOT_NAME} - Admin Login</h2>
    <div class="card">
      <form method="POST" action="/admin/login">
        <label>Username</label><br>
        <input name="username" placeholder="admin" required><br><br>

        <label>Password</label><br>
        <input name="password" type="password" placeholder="********" required><br><br>

        <button class="btn" type="submit">🔐 Login</button>
      </form>
      <p class="muted" style="margin-top:12px;">
        Tip: Set <b>ADMIN_USERNAME</b> and <b>ADMIN_PASSWORD</b> in ENV.
      </p>
    </div>
    """
    return web.Response(text=html_page("Admin Login", body), content_type="text/html")


async def route_admin_login_post(request: web.Request):
    data = await request.post()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    st = await get_settings()
    if username == st.get("admin_username") and password == st.get("admin_password"):
        token = make_admin_token(username)
        resp = web.HTTPFound("/admin/dashboard")
        set_cookie(resp, "admin_token", token, days=2)
        return resp

    body = """
    <h2>❌ Login Failed</h2>
    <div class="card">
      <p>Invalid username or password.</p>
      <a class="btn" href="/admin/login">🔁 Try Again</a>
    </div>
    """
    return web.Response(text=html_page("Login Failed", body), content_type="text/html")


async def route_admin_logout(request: web.Request):
    resp = web.HTTPFound("/admin/login")
    resp.del_cookie("admin_token")
    return resp


# ============================================================
#                 WEB: ADMIN DASHBOARD
# ============================================================

async def route_admin_dashboard(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users_count = await users_col.count_documents({})
    files_count = await files_col.count_documents({})
    bans_count = await bans_col.count_documents({})
    fsubs_count = await fsub_col.count_documents({})

    st = await get_settings()

    body = f"""
    <h2>📊 Admin Dashboard</h2>

    <div class="card">
      <p>👤 Users: <b>{users_count}</b></p>
      <p>📁 Files: <b>{files_count}</b></p>
      <p>🚫 Banned: <b>{bans_count}</b></p>
      <p>🔒 ForceSub(DB): <b>{fsubs_count}</b></p>
      <hr>
      <p class="muted">
        Web URL: <b>{WEB_URL}</b><br>
        Shortener: <b>{"ON" if st.get("shortner_enabled") else "OFF"}</b><br>
        ForceSub: <b>{"ON" if st.get("force_sub_enabled") else "OFF"}</b>
      </p>
    </div>

    <div class="card">
      <a class="btn" href="/admin/users">👤 Users</a>
      <a class="btn" href="/admin/files">📁 Files</a>
      <a class="btn" href="/admin/fsub">🔒 ForceSub</a>
      <a class="btn" href="/admin/settings">⚙️ Settings</a>
      <a class="btn" href="/admin/broadcast">📢 Broadcast</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>
    """
    return web.Response(text=html_page("Dashboard", body), content_type="text/html")


# ============================================================
#                 WEB: ADMIN USERS
# ============================================================

async def route_admin_users(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users_list = []
    async for u in users_col.find({}).sort("joined", -1).limit(50):
        users_list.append(u)

    body = """
    <h2>👤 Users (Last 50)</h2>
    <div class="card">
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>

    <div class="card">
      <table>
        <tr>
          <th>User ID</th>
          <th>Joined</th>
          <th>Action</th>
        </tr>
    """

    for u in users_list:
        uid = u["_id"]
        joined = str(u.get("joined", ""))[:19]
        banned = await bans_col.find_one({"_id": uid})
        if banned:
            action = f'<a class="btn" href="/admin/unban/{uid}">✅ Unban</a>'
        else:
            action = f'<a class="btn" href="/admin/ban/{uid}">🚫 Ban</a>'

        body += f"""
        <tr>
          <td>{uid}</td>
          <td class="muted">{joined}</td>
          <td>{action}</td>
        </tr>
        """

    body += """
      </table>
    </div>
    """
    return web.Response(text=html_page("Users", body), content_type="text/html")


async def route_admin_ban(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    uid = safe_int(request.match_info["user_id"])
    if uid:
        await ban_user(uid, OWNER_ID)

    raise web.HTTPFound("/admin/users")


async def route_admin_unban(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    uid = safe_int(request.match_info["user_id"])
    if uid:
        await unban_user(uid)

    raise web.HTTPFound("/admin/users")
    # ============================================================
#                 WEB: ADMIN FILES
# ============================================================

async def route_admin_files(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    files_list = []
    async for f in files_col.find({}).sort("created_at", -1).limit(50):
        files_list.append(f)

    body = """
    <h2>📁 Files (Last 50)</h2>
    <div class="card">
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>

    <div class="card">
      <table>
        <tr>
          <th>File ID</th>
          <th>Owner</th>
          <th>Uploaded</th>
          <th>Action</th>
        </tr>
    """

    for f in files_list:
        fid = f["_id"]
        owner = f.get("owner", "Unknown")
        created = str(f.get("created_at", ""))[:19]
        action = f'<a class="btn" href="/admin/deletefile/{fid}">🗑 Delete</a>'
        body += f"""
        <tr>
          <td>{fid}</td>
          <td>{owner}</td>
          <td class="muted">{created}</td>
          <td>{action}</td>
        </tr>
        """

    body += """
      </table>
    </div>
    """
    return web.Response(text=html_page("Files", body), content_type="text/html")


async def route_admin_deletefile(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    fid = request.match_info["file_id"]
    await files_col.delete_one({"_id": fid})

    raise web.HTTPFound("/admin/files")


# ============================================================
#                 WEB: ADMIN FORCE SUB
# ============================================================

async def route_admin_fsub(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    fsubs_list = []
    async for f in fsub_col.find({}).sort("added_at", -1).limit(50):
        fsubs_list.append(f)

    body = """
    <h2>🔒 Force Subscription</h2>
    <div class="card">
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>

    <div class="card">
      <form method="POST" action="/admin/fsub/add">
        <input name="channel" placeholder="Telegram channel username" required>
        <button class="btn" type="submit">➕ Add</button>
      </form>
    </div>

    <div class="card">
      <table>
        <tr>
          <th>Channel</th>
          <th>Action</th>
        </tr>
    """

    for f in fsubs_list:
        channel = f.get("_id")
        body += f"""
        <tr>
          <td>{channel}</td>
          <td>
            <a class="btn" href="/admin/fsub/remove/{channel}">🗑 Remove</a>
          </td>
        </tr>
        """

    body += """
      </table>
    </div>
    """
    return web.Response(text=html_page("ForceSub", body), content_type="text/html")


async def route_admin_fsub_add(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    channel = (data.get("channel") or "").strip()
    if channel:
        await fsub_col.update_one({"_id": channel}, {"$set": {"added_at": datetime.utcnow()}}, upsert=True)

    raise web.HTTPFound("/admin/fsub")


async def route_admin_fsub_remove(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    channel = request.match_info["channel"]
    await fsub_col.delete_one({"_id": channel})

    raise web.HTTPFound("/admin/fsub")


# ============================================================
#                 WEB: ADMIN SETTINGS
# ============================================================

async def route_admin_settings(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    st = await get_settings()

    body = f"""
    <h2>⚙️ Settings</h2>
    <div class="card">
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>

    <div class="card">
      <form method="POST" action="/admin/settings">
        <label>Admin Username</label><br>
        <input name="admin_username" value="{st.get('admin_username', '')}" required><br><br>

        <label>Admin Password</label><br>
        <input name="admin_password" type="password" value="{st.get('admin_password', '')}" required><br><br>

        <label>Bot Name</label><br>
        <input name="bot_name" value="{st.get('bot_name', BOT_NAME)}" required><br><br>

        <label>Shortener Enabled</label>
        <input type="checkbox" name="shortner_enabled" {"checked" if st.get("shortner_enabled") else ""}><br><br>

        <label>ForceSub Enabled</label>
        <input type="checkbox" name="force_sub_enabled" {"checked" if st.get("force_sub_enabled") else ""}><br><br>

        <button class="btn" type="submit">💾 Save Settings</button>
      </form>
    </div>
    """
    return web.Response(text=html_page("Settings", body), content_type="text/html")


async def route_admin_settings_post(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    updates = {
        "admin_username": data.get("admin_username"),
        "admin_password": data.get("admin_password"),
        "bot_name": data.get("bot_name"),
        "shortner_enabled": bool(data.get("shortner_enabled")),
        "force_sub_enabled": bool(data.get("force_sub_enabled"))
    }
    await settings_col.update_one({"_id": "config"}, {"$set": updates}, upsert=True)

    raise web.HTTPFound("/admin/settings")


# ============================================================
#                 WEB: ADMIN BROADCAST
# ============================================================

async def route_admin_broadcast(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    body = """
    <h2>📢 Broadcast Message</h2>
    <div class="card">
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
      <a class="btn" href="/admin/logout">🚪 Logout</a>
    </div>

    <div class="card">
      <form method="POST" action="/admin/broadcast">
        <textarea name="message" rows="6" placeholder="Message to broadcast..." required></textarea><br><br>
        <button class="btn" type="submit">📤 Send</button>
      </form>
    </div>
    """
    return web.Response(text=html_page("Broadcast", body), content_type="text/html")


async def route_admin_broadcast_post(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    data = await request.post()
    msg = data.get("message")
    if msg:
        await broadcast_to_users(msg)

    body = f"""
    <h2>✅ Broadcast Sent</h2>
    <div class="card">
      <p>Message sent to all users.</p>
      <a class="btn" href="/admin/dashboard">⬅️ Back</a>
    </div>
    """
    return web.Response(text=html_page("Broadcast Sent", body), content_type="text/html")
    
  # ============================================================
#                 HELPER FUNCTIONS
# ============================================================

# Check if request comes from admin
async def require_admin(request: web.Request):
    admin_token = request.cookies.get("admin_token")
    st = await get_settings()
    expected = st.get("admin_token")
    return admin_token == expected


# Generate a secure admin token
def make_admin_token():
    import secrets
    return secrets.token_hex(16)


# Set cookie for admin
def set_cookie(resp: web.Response, key: str, value: str):
    resp.set_cookie(key, value, httponly=True, max_age=7*24*3600)  # 7 days


# Generate HTML page wrapper
def html_page(title: str, body: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>{title}</title>
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
        h2 {{ color: #333; }}
        .card {{ background: #fff; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .btn {{ display: inline-block; padding: 6px 12px; margin: 4px 2px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; border-bottom: 1px solid #ccc; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .muted {{ color: #888; font-size: 0.9em; }}
        input, textarea {{ width: 100%; padding: 6px; margin: 4px 0; }}
      </style>
    </head>
    <body>
      {body}
    </body>
    </html>
    """


# Safely convert to integer
def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ============================================================
#                 DATABASE HELPERS
# ============================================================

# Get bot settings
async def get_settings():
    st = await settings_col.find_one({"_id": "config"})
    if not st:
        # Create default settings
        token = make_admin_token()
        st = {
            "_id": "config",
            "admin_username": "admin",
            "admin_password": "admin123",
            "bot_name": BOT_NAME,
            "shortner_enabled": True,
            "force_sub_enabled": True,
            "admin_token": token
        }
        await settings_col.insert_one(st)
    return st


# Broadcast a message to all users
async def broadcast_to_users(message: str):
    cursor = users_col.find({})
    async for user in cursor:
        uid = user["_id"]
        try:
            # Example: send to Telegram bot
            await bot.send_message(uid, message)
        except Exception as e:
            print(f"Failed to send to {uid}: {e}")


# Ban a user
async def ban_user(user_id):
    await banned_col.update_one({"_id": user_id}, {"$set": {"banned": True}}, upsert=True)


# Unban a user
async def unban_user(user_id):
    await banned_col.delete_one({"_id": user_id})


# ============================================================
#                 APP STARTUP
# ============================================================

# Main app initialization
app = web.Application()

# -------------------------
# WEB ROUTES
# -------------------------
app.add_routes([
    # User routes
    web.get("/", route_index),
    web.get("/start", route_index),

    # Admin routes
    web.get("/admin/login", route_admin_login),
    web.post("/admin/login", route_admin_login_post),
    web.get("/admin/logout", route_admin_logout),
    web.get("/admin/dashboard", route_admin_dashboard),
    web.get("/admin/users", route_admin_users),
    web.get("/admin/deleteuser/{user_id}", route_admin_deleteuser),
    web.get("/admin/files", route_admin_files),
    web.get("/admin/deletefile/{file_id}", route_admin_deletefile),
    web.get("/admin/fsub", route_admin_fsub),
    web.post("/admin/fsub/add", route_admin_fsub_add),
    web.get("/admin/fsub/remove/{channel}", route_admin_fsub_remove),
    web.get("/admin/settings", route_admin_settings),
    web.post("/admin/settings", route_admin_settings_post),
    web.get("/admin/broadcast", route_admin_broadcast),
    web.post("/admin/broadcast", route_admin_broadcast_post),
])

# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    import aiohttp
    import asyncio
    import motor.motor_asyncio
    from datetime import datetime

    # Bot and MongoDB setup
    BOT_NAME = "MyFileBot"
    MONGO_URI = "mongodb://localhost:27017"
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client["file_bot_db"]
    users_col = db["users"]
    files_col = db["files"]
    fsub_col = db["fsub"]
    banned_col = db["banned"]
    settings_col = db["settings"]

    # Example placeholder for bot instance
    class DummyBot:
        async def send_message(self, user_id, message):
            print(f"Sending message to {user_id}: {message}")

    bot = DummyBot()

    web.run_app(app, host="0.0.0.0", port=8080)
    # ============================================================
#                   FILE RENAME SUPPORT
# ============================================================

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def handle_file_rename(client: Client, message: Message):
    await add_user(message.from_user.id)

    if await is_banned(message.from_user.id):
        return await message.reply_text("🚫 You are banned!")

    ok, fmsg, btns = await force_sub_check(client, message.from_user.id)
    if not ok:
        btns.append([InlineKeyboardButton("🔁 Try Again", url=f"https://t.me/{client.me.username}?start=checksub")])
        return await message.reply_text(
            fmsg,
            reply_markup=InlineKeyboardMarkup(btns),
            disable_web_page_preview=True
        )

    media = message.document or message.video or message.audio or message.photo
    if not media:
        return

    # Default filename
    file_name = getattr(media, "file_name", "File")
    file_size = getattr(media, "file_size", 0) or 0
    tg_file_id = media.file_id
    file_unique_id = media.file_unique_id

    # Check caption for rename
    if message.caption and message.caption.lower().startswith("rename:"):
        new_name = message.caption[7:].strip()
        if new_name:
            file_name = new_name

    # Save file to DB
    await save_file_to_db(file_unique_id, tg_file_id, file_name, file_size, message.from_user.id)

    # Links
    code = b64e(file_unique_id)
    bot_link = make_bot_link(client.me.username, code)
    watch_url = await get_short(make_watch_url(file_unique_id))
    dl_url = await get_short(make_dl_url(file_unique_id))
    bot_link = await get_short(bot_link)

    text = (
        "✅ **File Stored Successfully!**\n\n"
        f"📁 **Name:** `{file_name}`\n"
        f"📦 **Size:** `{humanbytes(file_size)}`\n\n"
        "🔗 **Share Links:**\n"
        f"🤖 Bot: `{bot_link}`\n"
        f"🎬 Watch: `{watch_url}`\n"
        f"⬇️ Download: `{dl_url}`\n"
    )

    buttons = [
        [InlineKeyboardButton("🤖 Bot Link", url=bot_link)],
        [InlineKeyboardButton("🎬 Watch / Stream", url=watch_url)],
        [InlineKeyboardButton("⬇️ Download", url=dl_url)],
    ]

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# ============================================================
#                WEB STREAM AND DOWNLOAD ROUTES
# ============================================================

async def route_watch(request: web.Request):
    file_id = request.match_info["file_id"].strip()
    data = await files_col.find_one({"_id": file_id})
    if not data:
        return web.Response(text="File not found!", status=404)
    file_name = data.get("name", "File")
    mime = data.get("mime", "application/octet-stream")
    dl_url = make_dl_url(file_id)

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>{file_name}</title></head>
    <body style="text-align:center;font-family:sans-serif;">
        <h2>📁 {file_name}</h2>
        <video width="80%" height="auto" controls>
            <source src="{dl_url}" type="{mime}">
            Your browser does not support HTML5 video.
        </video>
        <br><br>
        <a href="{dl_url}" download>⬇️ Download</a>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


async def route_download(request: web.Request):
    file_id = request.match_info["file_id"].strip()
    data = await files_col.find_one({"_id": file_id})
    if not data:
        return web.Response(text="File not found!", status=404)

    tg_file_id = data["tg_file_id"]
    file_name = data.get("name", "file.bin")
    mime = data.get("mime", "application/octet-stream")
    size = int(data.get("size", 0))

    # Range support
    range_header = request.headers.get("Range", None)
    start = 0
    end = size - 1

    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            if m.group(2):
                end = int(m.group(2))
            else:
                end = size - 1
    length = end - start + 1

    headers = {
        "Content-Type": mime,
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Cache-Control": "no-store",
    }

    status = 206 if range_header else 200
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    resp = web.StreamResponse(status=status, headers=headers)
    await resp.prepare(request)

    try:
        async for chunk in bot.stream_media(message=None, file_id=tg_file_id, offset=start, limit=length):
            await resp.write(chunk)
    except Exception as e:
        return web.Response(text=f"Stream error: {e}", status=500)

    await resp.write_eof()
    return resp

# ============================================================
#                   RUN BOT + WEB
# ============================================================

async def run_all():
    await bot.start()
    me = await bot.get_me()
    print("🤖 Bot Started:", me.username)

    app = web.Application()
    app.router.add_get("/watch/{file_id}", route_watch)
    app.router.add_get("/dl/{file_id}", route_download)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("🌐 Web server running on PORT:", PORT)
    print("🌐 WEB_URL:", WEB_URL)

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_all())
