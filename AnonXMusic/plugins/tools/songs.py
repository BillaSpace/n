import os
import asyncio
import yt_dlp
import time
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic import app
from config import LOGGER_ID

# Define directories and constants
DOWNLOADS_DIR = "downloads"
COOKIES_DIR = "cookies"
COOKIES_FILE = os.path.join(COOKIES_DIR, "cookies.txt")
MIN_FILE_SIZE = 51200  # Minimum file size in bytes to avoid corrupted downloads
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)

# Spam protection variables
user_last_message_time = {}
user_command_count = {}
SPAM_THRESHOLD = 2
SPAM_WINDOW_SECONDS = 5

def download_thumbnail(url: str, thumb_name: str) -> str | None:
    """Download thumbnail from URL and save it to thumb_name."""
    try:
        response = requests.get(url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            with open(thumb_name, "wb") as f:
                f.write(response.content)
            return thumb_name
        return None
    except Exception:
        return None

def parse_duration(duration: str) -> int:
    """Parse duration string (e.g., 'HH:MM:SS' or 'MM:SS') to seconds."""
    try:
        parts = list(map(int, duration.split(":")))
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h, m, s = 0, parts[0], parts[1]
        else:
            h, m, s = 0, 0, parts[0]
        return h * 3600 + m * 60 + s
    except Exception:
        return 0

@app.on_message(filters.command(["song", "music"]))
async def download_song(client: Client, message: Message):
    user_id = message.from_user.id
    current_time = time()

    # Spam protection
    last_message_time = user_last_message_time.get(user_id, 0)
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            hu = await message.reply_text(
                f"**{message.from_user.mention} ᴘʟᴇᴀsᴇ ᴅᴏɴᴛ ᴅᴏ sᴘᴀᴍ, ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 5 sᴇᴄ**"
            )
            await asyncio.sleep(3)
            await hu.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    # Extract query from the message
    query = " ".join(message.command[1:])
    if not query:
        await message.reply("Please provide a song name or URL to search for.")
        return

    # Searching for the song
    m = await message.reply("🔄 **Searching...**")
    try:
        results = (await VideosSearch(query, limit=1).next()).get("result", [])
        if not results:
            await m.edit("**No results found. Please make sure you typed the correct song name.**")
            return

        result = results[0]
        link = result.get("link")
        title = result.get("title", "Unknown")
        thumbnail = result.get("thumbnails", [{}])[0].get("url")
        duration = result.get("duration", "0:00")
        views = result.get("viewCount", {}).get("text", "Unknown")
        channel_name = result.get("channel", {}).get("name", "Unknown")
        video_id = result.get("id")

        # Download thumbnail
        thumb_name = f"{DOWNLOADS_DIR}/{title.replace('/', '_')}.jpg"
        thumb_path = await asyncio.to_thread(download_thumbnail, thumbnail, thumb_name)

        # yt-dlp options
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{DOWNLOADS_DIR}/%(id)s.%(ext)s",
            "geo_bypass": True,
            "nocheckcertificate": True,
            "quiet": True,
            "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        # Download audio
        await m.edit("📥 **Downloading...**")
        audio_file = f"{DOWNLOADS_DIR}/{video_id}.mp3"
        
        if os.path.exists(audio_file):
            pass  # File already exists, skip download
        else:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            if not os.path.exists(audio_file) or os.path.getsize(audio_file) < MIN_FILE_SIZE:
                await m.edit("❌ **Failed to download the song or file is corrupted.**")
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)
                return

        # Parse duration
        dur = parse_duration(duration)

        # Create a copy of the file for the logger
        logger_file = f"{DOWNLOADS_DIR}/{video_id}_logger_{int(time.time())}.mp3"
        if os.path.exists(audio_file):
            import shutil
            shutil.copy(audio_file, logger_file)

        # Caption for both user and logger
        caption = f"📻 <b><a href=\"{link}\">{title}</a></b>\n🕒 <b>Duration:</b> {duration}\n🔧 <b>Powered by:</b> <a href=\"https://t.me/BillaSpace\">Space-X API</a>"
        logger_caption = f"{caption}\n👤 <b>Requested by:</b> {message.from_user.mention}"

        # Send audio to LOGGER_ID
        try:
            await client.send_audio(
                chat_id=LOGGER_ID,
                audio=logger_file,
                title=title,
                performer=BillaSpace,
                duration=dur,
                caption=logger_caption,
                thumb=thumb_path if thumb_path else None
            )
        except Exception:
            pass  # Silently handle logger ID errors

        # Send audio to user
        await m.edit("📤 **Uploading...**")
        await message.reply_audio(
            audio=audio_file,
            thumb=thumb_path,
            title=title,
            duration=dur,
            caption=caption,
            performer=channel_name,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎧 More Music", url="https://t.me/BillaSpace")],
                [InlineKeyboardButton("💻 Associated with", url="https://t.me/BillaCore")]
            ])
        )

        # Cleanup files after 5 minutes
        async def cleanup_files():
            await asyncio.sleep(300)  # 5 minutes
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                if os.path.exists(logger_file):
                    os.remove(logger_file)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass

        asyncio.create_task(cleanup_files())
        await m.delete()

    except Exception as e:
        await m.edit("⚠️ **An error occurred! Please try again later.**")