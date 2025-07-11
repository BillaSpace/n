import os
import time
import asyncio
import requests
import yt_dlp
from collections import defaultdict

from AnonXMusic import app
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch
from config import API_URL2, LOGGER_ID as SONG_DUMP_ID

DOWNLOADS_DIR = "downloads"
COOKIES_PATH = "cookies/cookies.txt"
MAX_RETRIES = 3
SPAM_LIMIT = 5
SPAM_WINDOW = 60  # seconds
BLOCK_DURATION = 600  # 10 minutes

user_usage = defaultdict(list)
user_blocked = {}

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

class QuietLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): print(f"[yt-dlp error] {msg}")

def parse_duration(duration_str):
    try:
        parts = duration_str.split(":")
        return sum(int(x) * 60**i for i, x in enumerate(reversed(parts)))
    except Exception:
        return 0

def download_thumbnail(url: str, file_path: str):
    try:
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code == 200:
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return file_path
    except Exception as e:
        print(f"[Thumbnail] Error: {e}")
    return None

async def cleanup_files(audio_file, thumb_path, user_msg, reply_msg):
    await asyncio.sleep(300)  # 5 minutes

    try:
        # Skip deletion only for the logger/dump channel
        if user_msg.chat.id != SONG_DUMP_ID:
            # Try deleting from private, group, or supergroup
            try:
                await reply_msg.delete()
            except Exception as e:
                print(f"[Cleanup] Failed to delete reply message: {e}")
            try:
                await user_msg.delete()
            except Exception as e:
                print(f"[Cleanup] Failed to delete user message: {e}")
    except Exception as e:
        print(f"[Cleanup] Message deletion error: {e}")

    try:
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
    except Exception as e:
        print(f"[Cleanup] File deletion error: {e}")

async def download_audio(url, video_id, title, m):
    output = os.path.join(DOWNLOADS_DIR, f"{video_id}_{int(time.time())}.m4a")
    progress_msg = m

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get("_percent_str", "").strip()
            eta = d.get("eta", 0)
            speed = d.get("_speed_str", "N/A").strip()
            text = f"📥 Downloading...\n\n<b>Progress:</b> {percent}\n<b>ETA:</b> {eta}s\n<b>Speed:</b> {speed}"
            try:
                asyncio.create_task(progress_msg.edit(text))
            except:
                pass

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": output,
        "noplaylist": True,
        "quiet": True,
        "logger": QuietLogger(),
        "progress_hooks": [progress_hook],
        "cookiefile": COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
        "no_warnings": True,
        "ignoreerrors": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "user_agent": "Mozilla/5.0",
    }

    for attempt in range(MAX_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(output):
                return output
        except Exception as e:
            print(f"[yt-dlp] Attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2)
    return None

@app.on_message(filters.command(["song", "music"]) & filters.text)
async def song_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    query = " ".join(message.command[1:])
    now = time.time()

    if user_id in user_blocked and now < user_blocked[user_id]:
        wait = int(user_blocked[user_id] - now)
        return await message.reply(f"<b>You're temporarily blocked for spamming.\nTry again in {wait} seconds.</b>")

    usage_list = user_usage[user_id]
    usage_list = [t for t in usage_list if now - t < SPAM_WINDOW]
    usage_list.append(now)
    user_usage[user_id] = usage_list

    if len(usage_list) > SPAM_LIMIT:
        user_blocked[user_id] = now + BLOCK_DURATION
        try:
            await app.send_message(
                SONG_DUMP_ID,
                f"🚫 <b>Blocked:</b> {user_name} ({user_id}) for spamming /song ({SPAM_LIMIT}+ uses in {SPAM_WINDOW}s)."
            )
        except: pass
        return await message.reply("<b>You're blocked for 10 minutes due to spamming.</b>")

    try:
        await app.send_message(
            SONG_DUMP_ID,
            f"🎵 <b>{user_name}</b> (ID: <code>{user_id}</code>) used /song command.\n🔍 <b>Query:</b> <code>{query}</code>",
        )
    except: pass

    if not query:
        return await message.reply("<b>Give me a song name or YouTube URL to download.</b>")

    # ✅ Normalize YouTube Music URLs
    if "music.youtube.com" in query:
        query = query.replace("music.youtube.com", "www.youtube.com")

    if "playlist?" in query or "list=" in query:
        return await message.reply("<b>Playlists are not allowed. Only single videos.</b>")

    m = await message.reply("<b>🔎 Searching the song...</b>")

    try:
        search = VideosSearch(query, limit=MAX_RETRIES)
        search_results = await search.next()
        if not search_results.get("result"):
            return await m.edit("<b>No results found for your query.</b>")
    except Exception as e:
        print(f"[Search] Error: {e}")
        return await m.edit("<b>Search error occurred. Please try again.</b>")

    result = search_results["result"][0]
    video_id = result.get("id")
    if not video_id:
        return await m.edit("<b>Invalid video found. Try another query.</b>")

    link = f"https://www.youtube.com/watch?v={video_id}"
    title = result.get("title", "Unknown")[:60]
    thumbnail = result.get("thumbnails", [{}])[0].get("url")
    duration = result.get("duration", "0:00")
    channel_name = result.get("channel", {}).get("name", "Unknown")

    thumb_name = f"{DOWNLOADS_DIR}/{title.replace('/', '_')}.jpg"
    thumb_path = await asyncio.to_thread(download_thumbnail, thumbnail, thumb_name)

    audio_file = await download_audio(link, video_id, title, m)

    if not audio_file and API_URL2 and video_id:
        api_url = f"{API_URL2}?direct&id={video_id}"
        try:
            r = requests.get(api_url, stream=True, timeout=10)
            if r.ok and "audio" in r.headers.get("content-type", ""):
                audio_file = f"{DOWNLOADS_DIR}/{video_id}.mp3"
                with open(audio_file, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            print(f"[API] Download failed: {e}")

    if not audio_file:
        try:
            await app.send_message(
                SONG_DUMP_ID,
                f"❌ <b>Download failed for:</b> {query}\n👤 <b>User:</b> {user_name} ({user_id})",
            )
        except: pass
        return await m.edit("<b>Failed to download song. Try a different one.</b>")

    dur = parse_duration(duration)
    performer_name = app.name or "BillaMusic"

    caption = (
        f"📻 <b><a href=\"{link}\">{title}</a></b>\n"
        f"🕒 Duration: {duration}\n"
        f"🎙️ By: {channel_name}\n\n"
        f"<i>Powered by Space-X Ashlyn API</i>"
    )

    await m.edit("🎧 Uploading your song...")

    try:
        reply_msg = await message.reply_audio(
            audio=audio_file,
            title=title,
            performer=performer_name,
            duration=dur,
            caption=caption,
            thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎧😄 More Songs", url="https://t.me/BillaSpace")]
            ])
        )

        await app.send_audio(
            chat_id=SONG_DUMP_ID,
            audio=audio_file,
            title=title,
            performer=performer_name,
            duration=dur,
            caption=caption,
            thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
        )

        await m.delete()
        asyncio.create_task(cleanup_files(audio_file, thumb_path, message, reply_msg))

    except Exception as e:
        print(f"[Upload] Error: {e}")
        return await m.edit("<b>Failed to upload the song. Please try again.</b>")
