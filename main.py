============================================================

UltraPro FileStore - SINGLE FILE FULL ROOT (PART 1/2)

Includes:

- File Store + Share Links

- Web Stream + Range Support

- Shortener

- Multi ForceSub (ENV + DB)

- Users DB + Files DB

- Admin Login System (UI in PART 2)

============================================================

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

============================================================

CONFIG

============================================================

API_ID = int(os.getenv("API_ID", "27806628"))
API_HASH = os.getenv("API_HASH", "25d88301e886b82826a525b7cf52e090")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8114942266:AAFtInLffruUXodXhf-1bAponngzCI9bRxg")

OWNER_ID = int(os.getenv("OWNER_ID", "8525952693"))

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Bosshub:JMaff0WvazwNxKky@cluster0.l0xcoc1.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("DB_NAME", "UltraProFileStore")

WEB_URL = os.getenv("WEB_URL", "https://file-store-ultra-pro-bot.onrender.com").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))

UI / Info

BOT_NAME = os.getenv("BOT_NAME", "UltraPro FileStore")
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "https://t.me/")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "https://t.me/")
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "https://radare.arzfun.com/api/tg/photo?id=AgACAgQAAxkBAAEL61Bplx4lS79xzA_Aw0u96UpcyLOd_gAC3A1rG0H75VPNP_NHb-SW5wEAAwIAA3gAAzoE")

Logs

LOG_CHANNEL = int(os.getenv("LOG_CHANNEL", "-1003559364122"))

Admin

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "UltraProSecretKeyChangeThis")

ForceSub

FORCE_SUB_ENABLED = os.getenv("FORCE_SUB_ENABLED", "true").lower() == "true"
FSUB_CHANNELS = os.getenv("FSUB_CHANNELS", "")  # "-1001,-1002"

Shortener

SHORTNER_ENABLED = os.getenv("SHORTNER_ENABLED", "false").lower() == "true"
SHORTNER_API = os.getenv("SHORTNER_API", "")
SHORTNER_API_KEY = os.getenv("SHORTNER_API_KEY", "")

Stream performance

STREAM_CHUNK_MB = int(os.getenv("STREAM_CHUNK_MB", "1"))
STREAM_CHUNK_SIZE = STREAM_CHUNK_MB * 1024 * 1024

Security

MAX_BROADCAST_PER_MIN = int(os.getenv("MAX_BROADCAST_PER_MIN", "25"))

============================================================

REQUIRED CHECK

============================================================

if API_ID == 0 or not API_HASH or not BOT_TOKEN:
raise SystemExit("❌ Missing API_ID / API_HASH / BOT_TOKEN")

if not MONGO_URI:
raise SystemExit("❌ Missing MONGO_URI")

if not WEB_URL:
raise SystemExit("❌ Missing WEB_URL")

============================================================

DATABASE

============================================================

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo[DB_NAME]

users_col = db["users"]
files_col = db["files"]
bans_col = db["bans"]
fsub_col = db["fsub_channels"]
settings_col = db["settings"]
clones_col = db["clones"]  # ready for future

============================================================

BOT INIT

============================================================

bot = Client(
"UltraProSingleFile",
api_id=API_ID,
api_hash=API_HASH,
bot_token=BOT_TOKEN,
in_memory=True
)

============================================================

GLOBAL CACHES

============================================================

CACHE = {
"fsub_channels": [],
"fsub_last": 0,
"settings": {},
"settings_last": 0
}

============================================================

SMALL UTILITIES

============================================================

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

============================================================

DATABASE HELPERS

============================================================

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

============================================================

SETTINGS (DB + CACHE)

============================================================

async def get_settings(force: bool = False) -> Dict[str, Any]:
"""
Loads settings from DB and caches them.
"""
t = int(datetime.datetime.utcnow().timestamp())
if not force and CACHE["settings"] and (t - CACHE["settings_last"] < 10):
return CACHE["settings"]

doc = await settings_col.find_one({"_id": "settings"}) or {}  
doc.pop("_id", None)  

# defaults  
doc.setdefault("shortner_enabled", SHORTNER_ENABLED)  
doc.setdefault("force_sub_enabled", FORCE_SUB_ENABLED)  
doc.setdefault("admin_username", ADMIN_USERNAME)  
doc.setdefault("admin_password", ADMIN_PASSWORD)  
doc.setdefault("site_name", BOT_NAME)  

CACHE["settings"] = doc  
CACHE["settings_last"] = t  
return doc

async def set_settings(new_settings: Dict[str, Any]):
await settings_col.update_one(
{"_id": "settings"},
{"$set": {"_id": "settings", **new_settings}},
upsert=True
)
await get_settings(force=True)

============================================================

FORCE SUB (ENV + DB)

============================================================

async def get_all_fsub_channels(force: bool = False) -> List[int]:
"""
Returns unique list of channels from ENV + DB.
Cached for performance.
"""
t = int(datetime.datetime.utcnow().timestamp())
if not force and CACHE["fsub_channels"] and (t - CACHE["fsub_last"] < 20):
return CACHE["fsub_channels"]

channels: List[int] = []  

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

channels = list(dict.fromkeys(channels))  

CACHE["fsub_channels"] = channels  
CACHE["fsub_last"] = t  
return channels

async def add_fsub_channel(chat_id: int):
await fsub_col.update_one({"_id": int(chat_id)}, {"$set": {"_id": int(chat_id)}}, upsert=True)
await get_all_fsub_channels(force=True)

async def remove_fsub_channel(chat_id: int):
await fsub_col.delete_one({"_id": int(chat_id)})
await get_all_fsub_channels(force=True)

async def force_sub_check(client: Client, user_id: int) -> Tuple[bool, str, list]:
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
        missing += 1  

if missing > 0:  
    return False, "🔒 You must join all channels to use this bot.", buttons  

return True, "", []

============================================================

SHORTENER (API)

============================================================

async def get_short(url: str) -> str:
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

            # supports many common formats  
            for k in ("shortenedUrl", "short", "short_url", "result_url", "url"):  
                if k in data and data[k]:  
                    return data[k]  
except:  
    pass  

return url

============================================================

ADMIN CHECK

============================================================

def is_owner(user_id: int) -> bool:
return int(user_id) == int(OWNER_ID)

============================================================

BOT: START

============================================================

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
await add_user(message.from_user.id)

if await is_banned(message.from_user.id):  
    return await message.reply_text("🚫 You are banned from using this bot.")  

ok, fmsg, btns = await force_sub_check(client, message.from_user.id)  
if not ok:  
    btns.append([InlineKeyboardButton("🔁 Try Again", url=f"https://t.me/{client.me.username}?start=checksub")])  
    return await message.reply_text(  
        fmsg,  
        reply_markup=InlineKeyboardMarkup(btns),  
        disable_web_page_preview=True  
    )  

# open file from /start <code>  
if len(message.command) > 1 and message.command[1] != "checksub":  
    code = message.command[1].strip()  
    try:  
        file_unique_id = b64d(code)  
    except:  
        return await message.reply_text("❌ Invalid link code!")  

    data = await files_col.find_one({"_id": file_unique_id})  
    if not data:  
        return await message.reply_text("❌ File not found!")  

    watch = await get_short(make_watch_url(file_unique_id))  
    dl = await get_short(make_dl_url(file_unique_id))  

    btn = [  
        [InlineKeyboardButton("🎬 Watch / Stream", url=watch)],  
        [InlineKeyboardButton("⬇️ Download", url=dl)],  
        [InlineKeyboardButton("🤖 Get File in Bot", callback_data=f"getfile#{file_unique_id}")]  
    ]  

    return await message.reply_text(  
        f"📁 **File:** `{data.get('name','File')}`\n"  
        f"📦 **Size:** `{humanbytes(data.get('size',0))}`\n\n"  
        f"Choose option 👇",  
        reply_markup=InlineKeyboardMarkup(btn),  
        disable_web_page_preview=True  
    )  

st = await get_settings()  

buttons = [  
    [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{client.me.username}?startgroup=true")],  
    [  
        InlineKeyboardButton("🎬 Web Stream", url=WEB_URL),  
        InlineKeyboardButton("🌐 Admin Panel", url=f"{WEB_URL}/admin/login")  
    ],  
    [  
        InlineKeyboardButton("📢 Updates", url=UPDATES_CHANNEL),  
        InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)  
    ]  
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
    return await message.reply_photo(  
        START_IMAGE_URL,  
        caption=text,  
        reply_markup=InlineKeyboardMarkup(buttons)  
    )  

await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

============================================================

BOT: SAVE FILES

============================================================

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def save_file_handler(client: Client, message: Message):
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

tg_file_id = media.file_id  
file_unique_id = media.file_unique_id  
file_name = getattr(media, "file_name", None) or "File"  
file_size = getattr(media, "file_size", 0) or 0  

await save_file_to_db(file_unique_id, tg_file_id, file_name, file_size, message.from_user.id)  

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

============================================================

CALLBACK: SEND FILE IN BOT

============================================================

@bot.on_callback_query(filters.regex(r"^getfile#"))
async def getfile_callback(client: Client, query: CallbackQuery):
await add_user(query.from_user.id)

if await is_banned(query.from_user.id):  
    return await query.answer("🚫 You are banned!", show_alert=True)  

ok, _, _ = await force_sub_check(client, query.from_user.id)  
if not ok:  
    return await query.answer("Join channels first!", show_alert=True)  

file_unique_id = query.data.split("#", 1)[1].strip()  

data = await files_col.find_one({"_id": file_unique_id})  
if not data:  
    return await query.answer("File not found!", show_alert=True)  

try:  
    await query.message.reply_cached_media(  
        data["tg_file_id"],  
        caption=f"📁 `{data.get('name','File')}`"  
    )  
except:  
    await query.message.reply_text("❌ Telegram error while sending file.")  

await query.answer("✅ Sent!")

============================================================

BOT: OWNER COMMANDS

============================================================

@bot.on_message(filters.command("stats") & filters.private)
async def stats_cmd(client: Client, message: Message):
if not is_owner(message.from_user.id):
return

users = await users_col.count_documents({})  
files = await files_col.count_documents({})  
bans = await bans_col.count_documents({})  
fsubs = await fsub_col.count_documents({})  

await message.reply_text(  
    f"📊 **Stats**\n\n"  
    f"👤 Users: `{users}`\n"  
    f"📁 Files: `{files}`\n"  
    f"🚫 Banned: `{bans}`\n"  
    f"🔒 ForceSub Channels(DB): `{fsubs}`\n"  
)

@bot.on_message(filters.command("ban") & filters.private)
async def ban_cmd(client: Client, message: Message):
if not is_owner(message.from_user.id):
return

if len(message.command) < 2:  
    return await message.reply_text("Use: `/ban user_id`")  

user_id = safe_int(message.command[1])  
if not user_id:  
    return await message.reply_text("❌ Invalid user id")  

await ban_user(user_id, message.from_user.id)  
await message.reply_text(f"✅ Banned `{user_id}`")

@bot.on_message(filters.command("unban") & filters.private)
async def unban_cmd(client: Client, message: Message):
if not is_owner(message.from_user.id):
return

if len(message.command) < 2:  
    return await message.reply_text("Use: `/unban user_id`")  

user_id = safe_int(message.command[1])  
if not user_id:  
    return await message.reply_text("❌ Invalid user id")  

await unban_user(user_id)  
await message.reply_text(f"✅ Unbanned `{user_id}`")

@bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(client: Client, message: Message):
if not is_owner(message.from_user.id):
return

if not message.reply_to_message:  
    return await message.reply_text("Reply to a message to broadcast.")  

total = 0  
done = 0  
failed = 0  

start_time = datetime.datetime.utcnow()  

msg = await message.reply_text("📢 Broadcasting started...")  

async for u in users_col.find({}):  
    total += 1  
    uid = u["_id"]  
    try:  
        await message.reply_to_message.copy(uid)  
        done += 1  
    except:  
        failed += 1  

    # performance control  
    if total % MAX_BROADCAST_PER_MIN == 0:  
        await asyncio.sleep(60)  

    await asyncio.sleep(0.05)  

took = datetime.datetime.utcnow() - start_time  

await msg.edit_text(  
    f"✅ Broadcast Completed\n\n"  
    f"Total: `{total}`\n"  
    f"Done: `{done}`\n"  
    f"Failed: `{failed}`\n"  
    f"Time: `{took}`"  
)

============================================================

WEB: HTML HELPERS

============================================================

def html_page(title: str, body: str) -> str:
return f"""
<!doctype html>

<html>  
<head>  
  <meta charset="utf-8">  
  <meta name="viewport" content="width=device-width, initial-scale=1">  
  <title>{title}</title>  
  <style>  
    body {{  
      font-family: Arial, sans-serif;  
      margin: 0;  
      padding: 0;  
      background: #0b0b0f;  
      color: #fff;  
    }}  
    .wrap {{  
      max-width: 980px;  
      margin: auto;  
      padding: 18px;  
    }}  
    .card {{  
      background: #141421;  
      border: 1px solid rgba(255,255,255,0.08);  
      border-radius: 16px;  
      padding: 18px;  
      margin-top: 14px;  
      box-shadow: 0 10px 40px rgba(0,0,0,0.25);  
    }}  
    a {{  
      color: #7aa7ff;  
      text-decoration: none;  
    }}  
    .btn {{  
      display: inline-block;  
      padding: 10px 14px;  
      border-radius: 12px;  
      border: 1px solid rgba(255,255,255,0.12);  
      background: rgba(255,255,255,0.06);  
      color: #fff;  
      margin: 4px 0;  
    }}  
    input, textarea {{  
      width: 100%;  
      padding: 10px;  
      border-radius: 12px;  
      border: 1px solid rgba(255,255,255,0.12);  
      background: rgba(255,255,255,0.06);  
      color: #fff;  
      outline: none;  
    }}  
    table {{  
      width: 100%;  
      border-collapse: collapse;  
      margin-top: 10px;  
      overflow: hidden;  
      border-radius: 12px;  
    }}  
    th, td {{  
      padding: 10px;  
      border-bottom: 1px solid rgba(255,255,255,0.08);  
      text-align: left;  
      font-size: 14px;  
    }}  
    th {{  
      background: rgba(255,255,255,0.06);  
    }}  
    .muted {{  
      opacity: 0.75;  
    }}  
  </style>  
</head>  
<body>  
  <div class="wrap">  
    {body}  
  </div>  
</body>  
</html>  
"""  def set_cookie(resp: web.Response, key: str, value: str, days: int = 1):
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

============================================================

WEB: ROUTES BASIC

============================================================

async def route_home(request: web.Request):
st = await get_settings()
body = f"""
<h2>🎬 {st.get('site_name', BOT_NAME)} - Web Stream</h2>
<div class="card">
<p class="muted">
This server provides streaming & direct download for Telegram files.
</p>
<a class="btn" href="/admin/login">🌐 Admin Panel</a>
<a class="btn" href="{SUPPORT_GROUP}">💬 Support</a>
</div>
"""
return web.Response(text=html_page("UltraPro Stream", body), content_type="text/html")

async def route_watch(request: web.Request):
file_id = request.match_info["file_id"].strip()
data = await files_col.find_one({"_id": file_id})
if not data:
return web.Response(text="File not found!", status=404)

name = data.get("name", "Video")  
dl = make_dl_url(file_id)  

body = f"""  
<h2>🎬 {name}</h2>  
<div class="card">  
  <video width="100%" controls playsinline>  
    <source src="{dl}" type="{data.get('mime','video/mp4')}">  
  </video>  
  <br><br>  
  <a class="btn" href="{dl}">⬇️ Direct Download</a>  
</div>  
"""  
return web.Response(text=html_page(name, body), content_type="text/html")

============================================================

WEB: STREAM DOWNLOAD (RANGE)

============================================================

async def route_download(request: web.Request):
"""
High performance streaming with Range support.
Uses Pyrogram stream_media.
"""
file_id = request.match_info["file_id"].strip()
data = await files_col.find_one({"_id": file_id})
if not data:
return web.Response(text="File not found!", status=404)

tg_file_id = data["tg_file_id"]  
file_name = data.get("name", "file.bin")  
mime = data.get("mime", "application/octet-stream")  
size = int(data.get("size", 0))  

# Parse Range  
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

if start < 0:  
    start = 0  
if end >= size:  
    end = size - 1  
if start > end:  
    return web.Response(status=416, text="Invalid Range")  

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

============================================================

PART 2 WILL CONTINUE FROM HERE (ADMIN UI)

============================================================

In PART 2 you will get:

- /admin/login UI

- /admin/dashboard

- /admin/users (ban/unban)

- /admin/files (delete)

- /admin/fsub (add/remove)

- /admin/settings (shortener enable/disable)

- Run bot + web together

============================================================

UltraPro FileStore - SINGLE FILE FULL ROOT (PART 2/2)

Includes:

- Full Admin Panel UI

- Dashboard / Users / Files / FSub / Settings

- Ban / Unban / Delete file / Broadcast

- Bot + Web run together

============================================================

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

# show last 50 users  
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

============================================================

WEB: ADMIN FILES

============================================================

async def route_admin_files(request: web.Request):
if not await require_admin(request):
raise web.HTTPFound("/admin/login")

# last 50 files  
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
    <input name="chat_id" placeholder="-1001234567890" required>  
    <br><br>  
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
    <input name="site_name" value="{st.get('site_name', BOT_NAME)}" required>  
    <br><br>  
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
    <textarea name="text" rows="5" placeholder="Hello users..." required></textarea>  
    <br><br>  
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

============================================================

RUN BOT + WEB TOGETHER

============================================================

async def run_all():
await bot.start()
me = await bot.get_me()
print("🤖 Bot Started:", me.username)

app = build_web_app()  
runner = web.AppRunner(app)  
await runner.setup()  

site = web.TCPSite(runner, "0.0.0.0", PORT)  
await site.start()  

print("🌐 Web Started on PORT:", PORT)  
print("🌐 WEB_URL:", WEB_URL)  

while True:  
    await asyncio.sleep(3600)

if name == "main":
asyncio.get_event_loop().run_until_complete(run_all())
