import os
import asyncio

import time
import requests
import yt_dlp

from AnonXMusic import app
from youtubesearchpython.__future__ import VideosSearch
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import API_URL2, LOGGER_ID as SONG_DUMP_ID

DOWNLOADS_DIR = "downloads"
COOKIES_PATH = "cookies/cookies.txt"
MAX_RETRIES = 3

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)
if not os.path.exists("cookies"):
    os.makedirs("cookies")

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
    await asyncio.sleep(300)  # wait 5 minutes
    try:
        if reply_msg.chat.id != SONG_DUMP_ID:
            await reply_msg.delete()
            await user_msg.delete()
    except Exception as e:
        print(f"[Cleanup] Message deletion error: {e}")
    try:
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
    except Exception as e:
        print(f"[Cleanup] File deletion error: {e}")

async def download_audio(url, video_id, title):
    output = os.path.join(DOWNLOADS_DIR, f"{video_id}_{int(time.time())}.m4a")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
        "outtmpl": output,
        "noplaylist": True,
        "quiet": True,
        "cookiefile": COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
        "no_warnings": True,
        "ignoreerrors": True,
        "geo_bypass": True,  # Bypass geo-restrictions
        "nocheckcertificate": True,  # Handle SSL issues
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "extractor_args": {
            "youtube": {
                "skip_auth_checks": True,  # Skip age restriction checks
                "lang": "en",  # Set language to English
            }
        },
        "force_generic_extractor": False,
    }

    for attempt in range(MAX_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(output):
                return output
        except yt_dlp.utils.DownloadError as e:
            print(f"[yt-dlp] Attempt {attempt + 1} failed: {e}")
            if attempt == MAX_RETRIES - 1:
                return None
            await asyncio.sleep(2)  # Wait before retrying
    return None

@app.on_message(filters.command(["song", "music"]) & filters.text)
async def song_handler(client: Client, message: Message):
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("<b>Give me a song name or YouTube URL to download.</b>")

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

    await m.edit("📥 Downloading Lossless Song File...")
    audio_file = await download_audio(link, video_id, title)

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
        await m.edit("<b>Failed to download song. It may be restricted or unavailable. Try a different one.</b>")
        return

    dur = parse_duration(duration)
    caption = f"📻 <b><a href=\"{link}\">{title}</a></b>\n🕒 Duration: {duration}\n🎙️ By: {channel_name}"

    await m.edit("🎧 Uploading your song...")
    try:
        reply_msg = await message.reply_audio(
            audio=audio_file,
            title=title,
            performer=channel_name,
            duration=dur,
            caption=caption,
            thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎧 More", url="https://t.me/BillaSpace")]
            ])
        )
    except Exception as e:
        print(f"[Upload] Error: {e}")
        await m.edit("<b>Failed to upload the song. Please try again.</b>")
        return

    await m.delete()
    asyncio.create_task(cleanup_files(audio_file, thumb_path, message, reply_msg))
