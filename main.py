# ============================================================
# UltraPro FileStore - SINGLE FILE FULL ROOT (PART 1/2)
# ============================================================

import os
import re
import base64
import asyncio
import datetime
from typing import List, Tuple, Dict, Any

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
import aiohttp

# ============================================================
# CONFIG
# ============================================================

API_ID = int(os.getenv("API_ID", 27806628))
API_HASH = os.getenv("API_HASH", "25d88301e886b82826a525b7cf52e090")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8114942266:AAFtInLffruUXodXhf-1bAponngzCI9bRxg")

OWNER_ID = int(os.getenv("OWNER_ID", "8525952693"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Bosshub:JMaff0WvazwNxKky@cluster0.l0xcoc1.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "UltraProFileStore")

WEB_URL = os.getenv("WEB_URL", "http://localhost:8080").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))

BOT_NAME = os.getenv("BOT_NAME", "UltraPro FileStore")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

FORCE_SUB_ENABLED = os.getenv("FORCE_SUB_ENABLED", "true").lower() == "true"
FSUB_CHANNELS = os.getenv("FSUB_CHANNELS", "")

SHORTNER_ENABLED = os.getenv("SHORTNER_ENABLED", "false").lower() == "true"
SHORTNER_API = os.getenv("SHORTNER_API", "")
SHORTNER_API_KEY = os.getenv("SHORTNER_API_KEY", "")

STREAM_CHUNK_MB = int(os.getenv("STREAM_CHUNK_MB", "1"))
STREAM_CHUNK_SIZE = STREAM_CHUNK_MB * 1024 * 1024

# ============================================================
# REQUIRED CHECK
# ============================================================

if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URI]):
    raise SystemExit("❌ Missing required ENV values")

# ============================================================
# DATABASE
# ============================================================

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]

users_col = db.users
files_col = db.files
bans_col = db.bans
fsub_col = db.fsub_channels
settings_col = db.settings

# ============================================================
# BOT INIT
# ============================================================

bot = Client(
    "UltraProSingleFile",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ============================================================
# GLOBAL CACHE (OPTIMIZED)
# ============================================================

CACHE = {
    "settings": {},
    "settings_last": 0,
    "fsub": [],
    "fsub_last": 0
}

SEEN_USERS = set()
HTTP_SESSION = aiohttp.ClientSession()

# ============================================================
# UTILITIES
# ============================================================

def now():
    return datetime.datetime.utcnow()

def b64e(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")

def b64d(text: str) -> str:
    text += "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text).decode()

def humanbytes(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{round(size,2)} {unit}"
        size /= 1024
    return "PB"

def mime(name: str) -> str:
    name = name.lower()
    if name.endswith(".mp4"): return "video/mp4"
    if name.endswith(".mkv"): return "video/x-matroska"
    if name.endswith(".mp3"): return "audio/mpeg"
    if name.endswith(".pdf"): return "application/pdf"
    return "application/octet-stream"

# ============================================================
# DB HELPERS (OPTIMIZED)
# ============================================================

async def add_user(uid: int):
    if uid in SEEN_USERS:
        return
    SEEN_USERS.add(uid)
    await users_col.update_one(
        {"_id": uid},
        {"$setOnInsert": {"joined": now()}},
        upsert=True
    )

async def is_banned(uid: int) -> bool:
    return bool(await bans_col.find_one({"_id": uid}))

async def save_file(fid, tg_id, name, size, uid):
    await files_col.update_one(
        {"_id": fid},
        {"$set": {
            "tg": tg_id,
            "name": name,
            "size": size,
            "mime": mime(name),
            "from": uid,
            "date": now()
        }},
        upsert=True
    )

# ============================================================
# SETTINGS (CACHED)
# ============================================================

async def get_settings(force=False) -> Dict[str, Any]:
    ts = int(now().timestamp())
    if not force and CACHE["settings"] and ts - CACHE["settings_last"] < 60:
        return CACHE["settings"]

    s = await settings_col.find_one({"_id": "settings"}) or {}
    s.setdefault("force_sub_enabled", FORCE_SUB_ENABLED)
    s.setdefault("shortner_enabled", SHORTNER_ENABLED)

    CACHE["settings"] = s
    CACHE["settings_last"] = ts
    return s

# ============================================================
# FORCE SUB (FAST EXIT)
# ============================================================

async def get_fsub_channels() -> List[int]:
    ts = int(now().timestamp())
    if CACHE["fsub"] and ts - CACHE["fsub_last"] < 120:
        return CACHE["fsub"]

    ch = []
    if FSUB_CHANNELS:
        ch.extend(int(x) for x in FSUB_CHANNELS.split(",") if x.strip("-").isdigit())

    async for c in fsub_col.find({}):
        ch.append(int(c["_id"]))

    CACHE["fsub"] = list(set(ch))
    CACHE["fsub_last"] = ts
    return CACHE["fsub"]

async def force_sub_check(client, uid) -> Tuple[bool, str, list]:
    if not (await get_settings()).get("force_sub_enabled"):
        return True, "", []

    for ch in await get_fsub_channels():
        try:
            m = await client.get_chat_member(ch, uid)
            if m.status in ("left", "kicked"):
                chat = await client.get_chat(ch)
                url = chat.invite_link or f"https://t.me/{chat.username}"
                return False, "🔒 Join channel to continue", [
                    [InlineKeyboardButton(f"Join {chat.title}", url=url)]
                ]
        except:
            pass
    return True, "", []

# ============================================================
# SHORTENER (REUSED SESSION)
# ============================================================

async def short(url: str) -> str:
    s = await get_settings()
    if not s.get("shortner_enabled") or not SHORTNER_API:
        return url
    try:
        async with HTTP_SESSION.get(
            f"{SHORTNER_API}?api={SHORTNER_API_KEY}&url={url}"
        ) as r:
            j = await r.json(content_type=None)
            return j.get("short") or j.get("url") or url
    except:
        return url

# ============================================================
# BOT COMMANDS
# ============================================================

@bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message: Message):
    uid = message.from_user.id
    await add_user(uid)

    if await is_banned(uid):
        return await message.reply_text("🚫 You are banned")

    ok, txt, btn = await force_sub_check(client, uid)
    if not ok:
        return await message.reply_text(txt, reply_markup=InlineKeyboardMarkup(btn))

    if len(message.command) > 1:
        fid = b64d(message.command[1])
        f = await files_col.find_one({"_id": fid})
        if not f:
            return await message.reply_text("❌ File not found")

        w = await short(f"{WEB_URL}/watch/{fid}")
        d = await short(f"{WEB_URL}/dl/{fid}")

        return await message.reply_text(
            f"📁 {f['name']}\n📦 {humanbytes(f['size'])}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Watch", url=w)],
                [InlineKeyboardButton("Download", url=d)]
            ])
        )

    await message.reply_text(f"👋 Welcome to {BOT_NAME}\nSend a file")

# ============================================================
# FILE SAVE
# ============================================================

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def save_handler(client, message: Message):
    uid = message.from_user.id
    await add_user(uid)

    media = message.document or message.video or message.audio
    await save_file(
        media.file_unique_id,
        media.file_id,
        media.file_name or "File",
        media.file_size or 0,
        uid
    )

    link = f"https://t.me/{client.me.username}?start={b64e(media.file_unique_id)}"
    await message.reply_text(f"✅ Saved\n🔗 {link}")

# ============================================================
# WEB STREAM (RANGE OPTIMIZED)
# ============================================================

async def route_download(request):
    fid = request.match_info["file_id"]
    f = await files_col.find_one({"_id": fid})
    if not f:
        return web.Response(status=404)

    size = f["size"]
    start, end = 0, size - 1

    if request.headers.get("Range"):
        m = re.match(r"bytes=(\d+)-(\d*)", request.headers["Range"])
        if m:
            start = int(m.group(1))
            end = int(m.group(2) or end)

    resp = web.StreamResponse(
        status=206,
        headers={
            "Content-Type": f["mime"],
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1)
        }
    )
    await resp.prepare(request)

    async for chunk in bot.stream_media(
        f["tg"],
        offset=start,
        limit=end - start + 1,
        chunk_size=min(STREAM_CHUNK_SIZE, end - start + 1)
    ):
        await resp.write(chunk)

    await resp.write_eof()
    return resp

# ================= END OF PART 1 =================
============================================================
UltraPro FileStore - SINGLE FILE FULL ROOT (PART 2/2)
Includes:
Full Admin Panel UI
Dashboard / Users / Files / FSub / Settings
Ban / Unban / Delete file / Broadcast
Bot + Web run together
============================================================

from aiohttp import web

============================================================
WEB: ADMIN LOGIN PAGE
============================================================

async def route_admin_login(request: web.Request):
    if await require_admin(request):
        raise web.HTTPFound("/admin/dashboard")
    st = await get_settings()
    body = f"""
<h2>🌐 {st.get('site_name', BOT_NAME)} - Admin Login</h2>
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

============================================================
WEB: ADMIN DASHBOARD
============================================================

async def route_admin_dashboard(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users = await users_col.count_documents({})
    files = await files_col.count_documents({})
    bans = await bans_col.count_documents({})
    fsubs = await fsub_col.count_documents({})
    st = await get_settings()

    body = f"""
<h2>📊 Admin Dashboard</h2>
<div class="card">
  <p>👤 Users: <b>{users}</b></p>
  <p>📁 Files: <b>{files}</b></p>
  <p>🚫 Banned: <b>{bans}</b></p>
  <p>🔒 ForceSub(DB): <b>{fsubs}</b></p>
  <hr>
  <p class="muted">
    Web Stream URL: <b>{WEB_URL}</b><br>
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

============================================================
WEB: ADMIN USERS
============================================================

async def route_admin_users(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    users = []
    async for u in users_col.find({}).sort("joined", -1).limit(50):
        users.append(u)

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
    for u in users:
        uid = u["_id"]
        joined = str(u.get("joined", ""))[:19]
        banned = await bans_col.find_one({"_id": uid})
        action = f'<a class="btn" href="/admin/unban/{uid}">✅ Unban</a>' if banned else f'<a class="btn" href="/admin/ban/{uid}">🚫 Ban</a>'
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

============================================================
WEB: ADMIN FILES
============================================================

async def route_admin_files(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")

    files = []
    async for f in files_col.find({}).sort("date", -1).limit(50):
        files.append(f)

    body = """
<h2>📁 Files (Last 50)</h2>
<div class="card">
  <a class="btn" href="/admin/dashboard">⬅️ Back</a>
  <a class="btn" href="/admin/logout">🚪 Logout</a>
</div>
<div class="card">
  <table>
    <tr>
      <th>Name</th>
      <th>Size</th>
      <th>Links</th>
      <th>Action</th>
    </tr>
"""
    for f in files:
        fid = f["_id"]
        name = (f.get("name") or "File")[:40]
        size = humanbytes(int(f.get("size", 0)))
        watch = make_watch_url(fid)
        dl = make_dl_url(fid)
        body += f"""
<tr>
  <td>{name}</td>
  <td class="muted">{size}</td>
  <td>
    <a href="{watch}" target="_blank">Watch</a> |
    <a href="{dl}" target="_blank">DL</a>
  </td>
  <td>
    <a class="btn" href="/admin/file/delete/{fid}">🗑 Delete</a>
  </td>
</tr>
"""
    body += """
  </table>
</div>
"""
    return web.Response(text=html_page("Files", body), content_type="text/html")

async def route_admin_file_delete(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    fid = request.match_info["file_id"].strip()
    await files_col.delete_one({"_id": fid})
    raise web.HTTPFound("/admin/files")

============================================================
WEB: ADMIN FSUB
============================================================

async def route_admin_fsub(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    channels = await get_all_fsub_channels(force=True)

    body = """
<h2>🔒 Force Subscribe</h2>
<div class="card">
  <a class="btn" href="/admin/dashboard">⬅️ Back</a>
  <a class="btn" href="/admin/logout">🚪 Logout</a>
</div>
<div class="card">
  <form method="POST" action="/admin/fsub/add">
    <label>Add Channel ID</label><br>
    <input name="chat_id" placeholder="-1001234567890" required><br><br>
    <button class="btn" type="submit">➕ Add</button>
  </form>
</div>
<div class="card">
  <h3>Channels</h3>
  <table>
    <tr>
      <th>Chat ID</th>
      <th>Action</th>
    </tr>
"""
    for ch in channels:
        body += f"""
<tr>
  <td>{ch}</td>
  <td><a class="btn" href="/admin/fsub/remove/{ch}">❌ Remove</a></td>
</tr>
"""
    body += """
  </table>
  <p class="muted">
    ENV channels also work, but cannot be removed from panel.
  </p>
</div>
"""
    return web.Response(text=html_page("ForceSub", body), content_type="text/html")

async def route_admin_fsub_add(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    data = await request.post()
    chat_id = safe_int(data.get("chat_id"))
    if chat_id:
        await add_fsub_channel(chat_id)
    raise web.HTTPFound("/admin/fsub")

async def route_admin_fsub_remove(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    chat_id = safe_int(request.match_info["chat_id"])
    if chat_id:
        await remove_fsub_channel(chat_id)
    raise web.HTTPFound("/admin/fsub")

============================================================
WEB: ADMIN SETTINGS
============================================================

async def route_admin_settings(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    st = await get_settings(force=True)

    short_status = "ON ✅" if st.get("shortner_enabled") else "OFF ❌"
    fsub_status = "ON ✅" if st.get("force_sub_enabled") else "OFF ❌"

    body = f"""
<h2>⚙️ Settings</h2>
<div class="card">
  <a class="btn" href="/admin/dashboard">⬅️ Back</a>
  <a class="btn" href="/admin/logout">🚪 Logout</a>
</div>
<div class="card">
  <h3>Toggle Features</h3>
  <p>Shortener: <b>{short_status}</b></p>
  <a class="btn" href="/admin/settings/toggle_short">🔁 Toggle Shortener</a>
  <hr>
  <p>ForceSub: <b>{fsub_status}</b></p>
  <a class="btn" href="/admin/settings/toggle_fsub">🔁 Toggle ForceSub</a>
</div>
<div class="card">
  <h3>Admin Credentials</h3>
  <form method="POST" action="/admin/settings/admin">
    <label>Admin Username</label><br>
    <input name="admin_username" value="{st.get('admin_username','admin')}" required><br><br>
    <label>Admin Password</label><br>
    <input name="admin_password" value="{st.get('admin_password','admin123')}" required><br><br>
    <button class="btn" type="submit">💾 Save</button>
  </form>
</div>
<div class="card">
  <h3>Site Name</h3>
  <form method="POST" action="/admin/settings/site">
    <input name="site_name" value="{st.get('site_name', BOT_NAME)}" required><br><br>
    <button class="btn" type="submit">💾 Save</button>
  </form>
</div>
"""
    return web.Response(text=html_page("Settings", body), content_type="text/html")

async def route_admin_toggle_short(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    st = await get_settings(force=True)
    st["shortner_enabled"] = not bool(st.get("shortner_enabled"))
    await set_settings(st)
    raise web.HTTPFound("/admin/settings")

async def route_admin_toggle_fsub(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    st = await get_settings(force=True)
    st["force_sub_enabled"] = not bool(st.get("force_sub_enabled"))
    await set_settings(st)
    raise web.HTTPFound("/admin/settings")

async def route_admin_save_admin(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    data = await request.post()
    username = (data.get("admin_username") or "").strip()
    password = (data.get("admin_password") or "").strip()
    if username and password:
        st = await get_settings(force=True)
        st["admin_username"] = username
        st["admin_password"] = password
        await set_settings(st)
    raise web.HTTPFound("/admin/settings")

async def route_admin_save_site(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    data = await request.post()
    site_name = (data.get("site_name") or "").strip()
    if site_name:
        st = await get_settings(force=True)
        st["site_name"] = site_name
        await set_settings(st)
    raise web.HTTPFound("/admin/settings")

============================================================
WEB: ADMIN BROADCAST
============================================================

async def route_admin_broadcast(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    body = """
<h2>📢 Broadcast</h2>
<div class="card">
  <a class="btn" href="/admin/dashboard">⬅️ Back</a>
  <a class="btn" href="/admin/logout">🚪 Logout</a>
</div>
<div class="card">
  <form method="POST" action="/admin/broadcast">
    <label>Broadcast Text</label><br>
    <textarea name="text" rows="5" placeholder="Hello users..." required></textarea><br><br>
    <button class="btn" type="submit">🚀 Send Broadcast</button>
  </form>
  <p class="muted" style="margin-top:10px;">
    This broadcast sends text only (safe + fast).
  </p>
</div>
"""
    return web.Response(text=html_page("Broadcast", body), content_type="text/html")

async def route_admin_broadcast_post(request: web.Request):
    if not await require_admin(request):
        raise web.HTTPFound("/admin/login")
    data = await request.post()
    text = (data.get("text") or "").strip()
    if not text:
        raise web.HTTPFound("/admin/broadcast")

    total = 0
    done = 0
    failed = 0

    async for u in users_col.find({}):
        total += 1
        uid = u["_id"]
        try:
            await bot.send_message(uid, text)
            done += 1
        except:
            failed += 1
        if total % MAX_BROADCAST_PER_MIN == 0:
            await asyncio.sleep(60)
        await asyncio.sleep(0.05)

    body = f"""
<h2>✅ Broadcast Completed</h2>
<div class="card">
  <p>Total: <b>{total}</b></p>
  <p>Done: <b>{done}</b></p>
  <p>Failed: <b>{failed}</b></p>
  <a class="btn" href="/admin/dashboard">⬅️ Back Dashboard</a>
</div>
"""
    return web.Response(text=html_page("Broadcast Done", body), content_type="text/html")

============================================================
WEB APP INIT ROUTES
============================================================

def build_web_app() -> web.Application:
    app = web.Application()

    # public
    app.router.add_get("/", route_home)
    app.router.add_get("/watch/{file_id}", route_watch)
    app.router.add_get("/dl/{file_id}", route_download)

    # admin
    app.router.add_get("/admin/login", route_admin_login)
    app.router.add_post("/admin/login", route_admin_login_post)
    app.router.add_get("/admin/logout", route_admin_logout)

    app.router.add_get("/admin/dashboard", route_admin_dashboard)

    app.router.add_get("/admin/users", route_admin_users)
    app.router.add_get("/admin/ban/{user_id}", route_admin_ban)
    app.router.add_get("/admin/unban/{user_id}", route_admin_unban)

    app.router.add_get("/admin/files", route_admin_files)
    app.router.add_get("/admin/file/delete/{file_id}", route_admin_file_delete)

    app.router.add_get("/admin/fsub", route_admin_fsub)
    app.router.add_post("/admin/fsub/add", route_admin_fsub_add)
    app.router.add_get("/admin/fsub/remove/{chat_id}", route_admin_fsub_remove)

    app.router.add_get("/admin/settings", route_admin_settings)
    app.router.add_get("/admin/settings/toggle_short", route_admin_toggle_short)
    app.router.add_get("/admin/settings/toggle_fsub", route_admin_toggle_fsub)
    app.router.add_post("/admin/settings/admin", route_admin_save_admin)
    app.router.add_post("/admin/settings/site", route_admin_save_site)

    app.router.add_get("/admin/broadcast", route_admin_broadcast)
    app.router.add_post("/admin/broadcast", route_admin_broadcast_post)

    return app

# ============================================================
# WEB: WATCH / STREAM (MX PLAYER SUPPORT)
# ============================================================

async def route_watch(request: web.Request):
    file_id = request.match_info["file_id"].strip()
    data = await files_col.find_one({"_id": file_id})
    if not data:
        return web.Response(text="File not found!", status=404)

    name = data.get("name", "Video")
    dl_url = make_dl_url(file_id)
    mime = data.get("mime", "video/mp4")

    # Web streaming URL (browser)
    watch_url = dl_url

    # MX Player URL (direct media URL for MX Player)
    mx_player_url = dl_url

    body = f"""
<h2>🎬 {name}</h2>
<div class="card">
  <video width="100%" controls playsinline>
    <source src="{watch_url}" type="{mime}">
  </video>
  <br><br>
  <a class="btn" href="{dl_url}">⬇️ Direct Download</a>
  <a class="btn" href="intent:{mx_player_url}#Intent;package=com.mxtech.videoplayer.ad;type=video/*;end">▶️ Play in MX Player</a>
</div>
"""
    return web.Response(text=html_page(name, body), content_type="text/html")


# ============================================================
# WEB APP ROUTES (Part 2 additions)
# ============================================================

def build_web_app() -> web.Application:
    app = web.Application()

    # Public routes
    app.router.add_get("/", route_home)
    app.router.add_get("/watch/{file_id}", route_watch)
    app.router.add_get("/dl/{file_id}", route_download)

    # Admin routes
    app.router.add_get("/admin/login", route_admin_login)
    app.router.add_post("/admin/login", route_admin_login_post)
    app.router.add_get("/admin/logout", route_admin_logout)
    app.router.add_get("/admin/dashboard", route_admin_dashboard)

    app.router.add_get("/admin/users", route_admin_users)
    app.router.add_get("/admin/ban/{user_id}", route_admin_ban)
    app.router.add_get("/admin/unban/{user_id}", route_admin_unban)

    app.router.add_get("/admin/files", route_admin_files)
    app.router.add_get("/admin/file/delete/{file_id}", route_admin_file_delete)

    app.router.add_get("/admin/fsub", route_admin_fsub)
    app.router.add_post("/admin/fsub/add", route_admin_fsub_add)
    app.router.add_get("/admin/fsub/remove/{chat_id}", route_admin_fsub_remove)

    app.router.add_get("/admin/settings", route_admin_settings)
    app.router.add_get("/admin/settings/toggle_short", route_admin_toggle_short)
    app.router.add_get("/admin/settings/toggle_fsub", route_admin_toggle_fsub)
    app.router.add_post("/admin/settings/admin", route_admin_save_admin)
    app.router.add_post("/admin/settings/site", route_admin_save_site)

    app.router.add_get("/admin/broadcast", route_admin_broadcast)
    app.router.add_post("/admin/broadcast", route_admin_broadcast_post)

    return app


# ============================================================
# RUN BOT + WEB TOGETHER
# ============================================================

async def run_all():
    await bot.start()
    me = await bot.get_me()
    print(f"🤖 Bot started as @{me.username} ({me.id})")

    app = build_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server running at {WEB_URL}")

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except (KeyboardInterrupt, SystemExit):
        print("⛔ Shutting down bot and web server...")
