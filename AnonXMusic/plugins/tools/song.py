import os
import asyncio
import yt_dlp
import time
import re
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic import app
from config import LOGGER_ID, API_URL2

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

def extract_video_id(link: str) -> str:
    """Extracts the video ID from a YouTube or YouTube Music URL."""
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'music\.youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube or YouTube Music link provided.")

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

async def download_audio(link: str, video_id: str, title: str) -> str | None:
    """Download audio using cookies-based yt-dlp or API_URL2 as fallback."""
    audio_file = f"{DOWNLOADS_DIR}/{video_id}.mp3"

    # Check if file already exists
    if os.path.exists(audio_file) and os.path.getsize(audio_file) >= MIN_FILE_SIZE:
        return audio_file

    # Try cookies-based yt-dlp download
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
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [link])
        if os.path.exists(audio_file) and os.path.getsize(audio_file) >= MIN_FILE_SIZE:
            return audio_file
    except Exception as e:
        print(f"Cookies-based download failed: {e}")

    # Fallback to API_URL2
    if API_URL2:
        try:
            api_url = f"{API_URL2}?direct&id={video_id}"
            print(f"Trying API_URL2: {api_url}")
            response = requests.get(api_url, stream=True)
            if response.status_code == 200:
                os.makedirs(DOWNLOADS_DIR, exist_ok=True)
                with open(audio_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                if os.path.exists(audio_file) and os.path.getsize(audio_file) >= MIN_FILE_SIZE:
                    print(f"Downloaded {audio_file} via API_URL2")
                    return audio_file
                else:
                    print(f"API_URL2 download failed: File corrupted or too small")
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
            else:
                print(f"API_URL2 failed for {video_id}. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error with API_URL2 for {video_id}: {e}")
            if os.path.exists(audio_file):
                os.remove(audio_file)

    return None

async def cleanup_files(audio_file: str, thumb_path: str | None, message: Message, reply_message: Message):
    """Delete files and messages after 5 minutes, except in LOGGER_ID."""
    await asyncio.sleep(300)  # 5 minutes
    try:
        # Delete files
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)
        # Delete user message (in groups/supergroups or DM)
        if message.chat.id != LOGGER_ID:
            await message.delete()
        # Delete bot's reply message (audio message)
        if reply_message and reply_message.chat.id != LOGGER_ID:
            await reply_message.delete()
    except Exception as e:
        print(f"Cleanup failed: {e}")

@app.on_message(filters.command(["song", "music"]))
async def download_song(client: Client, message: Message):
    user_id = message.from_user.id
    current_time = time.time()

    # Spam protection
    last_message_time = user_last_message_time.get(user_id, 0)
    if current_time - last_message_time < SPAM_WINDOW_SECONDS:
        user_last_message_time[user_id] = current_time
        user_command_count[user_id] = user_command_count.get(user_id, 0) + 1
        if user_command_count[user_id] > SPAM_THRESHOLD:
            reply = await message.reply_text(
                f"{message.from_user.mention} Please avoid spamming. Try again after 5 seconds."
            )
            await asyncio.sleep(3)
            await reply.delete()
            return
    else:
        user_command_count[user_id] = 1
        user_last_message_time[user_id] = current_time

    # Extract query or URL from the message
    query = " ".join(message.command[1:])
    if not query:
        await message.reply("Please provide a YouTube or YouTube Music URL to download the song.")
        return

    # Check for playlist URLs
    if "playlist?list=" in query or "&list=" in query:
        reply = await message.reply("Playlists are not allowed. Please provide a single song URL.")
        await asyncio.sleep(5)
        await reply.delete()
        return

    # Validate YouTube or YouTube Music URL
    youtube_patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'music\.youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
    ]
    video_id = None
    for pattern in youtube_patterns:
        match = re.search(pattern, query)
        if match:
            video_id = match.group(1)
            break
    if not video_id:
        await message.reply("Please provide a valid YouTube or YouTube Music URL.")
        return

    link = f"https://www.youtube.com/watch?v={video_id}"

    # Searching for song details
    m = await message.reply("Searching...")
    try:
        results = (await VideosSearch(link, limit=1).next()).get("result", [])
        if not results:
            await m.edit("No results found for the provided URL.")
            return

        result = results[0]
        title = result.get("title", "Unknown")
        thumbnail = result.get("thumbnails", [{}])[0].get("url")
        duration = result.get("duration", "0:00")
        channel_name = result.get("channel", {}).get("name", "Unknown")

        # Download thumbnail
        thumb_name = f"{DOWNLOADS_DIR}/{title.replace('/', '_')}.jpg"
        thumb_path = await asyncio.to_thread(download_thumbnail, thumbnail, thumb_name)

        # Download audio
        await m.edit("Downloading audio...")
        audio_file = await download_audio(link, video_id, title)
        if not audio_file:
            await m.edit("Failed to download the song or file is corrupted.")
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
        caption = f"📻 <b><a href=\"{link}\">{title}</a></b>\n🕒 Duration: {duration}\n🔧 Powered by: <a href=\"https://t.me/BillaSpace\">Space-X API</a>"
        logger_caption = f"{caption}\n👤 Requested by: {message.from_user.mention}"

        # Send audio to LOGGER_ID
        try:
            await client.send_audio(
                chat_id=LOGGER_ID,
                audio=logger_file,
                title=title,
                performer="BillaSpace",
                duration=dur,
                caption=logger_caption,
                thumb=thumb_path if thumb_path else None
            )
        except Exception:
            pass  # Silently handle loggerMostly ID errors

        # Send audio to user
        await m.edit("Uploading audio...")
        reply_message = await message.reply_audio(
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

        # Schedule cleanup
        asyncio.create_task(cleanup_files(audio_file, thumb_path, message, reply_message))
        await m.delete()

    except Exception as e:
        await m.edit(f"An error occurred: {str(e)}. Please try again later.")
