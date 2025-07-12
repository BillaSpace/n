import asyncio
import os
import re
import json
from typing import Union
import requests
import random
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds
import aiohttp
import logging
from config import API_URL1, API_URL2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_video_id(link: str) -> str:
    """
    Extracts the video ID from YouTube or YouTube Music links.
    """
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:.*\?v=|.*\/)([0-9A-Za-z_-]{11})',
        r'music\.youtube\.com\/watch\?v=([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    raise ValueError(f"Invalid YouTube or YouTube Music link: {link}")

async def api_dl(video_id: str, mode: str = "audio") -> str:
    """
    Downloads audio or video using API_URL1 (primary) or API_URL2 (fallback for audio).
    Returns the file path if successful, None otherwise.
    """
    file_ext = "mp3" if mode == "audio" else "mp4"
    file_path = os.path.join("downloads", f"{video_id}.{file_ext}")
    
    if os.path.exists(file_path):
        logger.info(f"File {file_path} already exists")
        return file_path

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    os.makedirs("downloads", exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        # Try API_URL1
        if API_URL1:
            for attempt in range(1):
                try:
                    api_url1 = f"{API_URL1}?url={youtube_url}&downloadMode={mode}"
                    logger.info(f"Attempt {attempt + 1}: API_URL1 for {video_id}")
                    async with session.get(api_url1, timeout=10) as response:
                        if response.status != 200:
                            raise Exception(f"API_URL1 failed with status {response.status}")
                        data = await response.json()
                        if data.get("successful") != "success" or "url" not in data.get("data", {}):
                            raise Exception(f"API_URL1 invalid response: {data.get('message', 'Unknown error')}")
                        
                        download_url = data["data"]["url"]
                        filename = data["data"].get("filename", f"{video_id}.{file_ext}")
                        safe_filename = re.sub(r'[^\w\s.-]', '', filename).replace(' ', '_')
                        if not safe_filename.lower().endswith(f".{file_ext}"):
                            safe_filename = f"{video_id}.{file_ext}"
                        file_path = os.path.join("downloads", safe_filename)
                        
                        async with session.get(download_url, timeout=30) as dl_response:
                            if dl_response.status != 200:
                                raise Exception(f"Download failed with status {dl_response.status}")
                            with open(file_path, 'wb') as f:
                                while True:
                                    chunk = await dl_response.content.read(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            logger.info(f"Downloaded {file_path} via API_URL1")
                            return file_path
                except Exception as e:
                    logger.error(f"API_URL1 attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                    continue
            logger.warning(f"Max retries reached for API_URL1: {video_id}")

        # Fallback to API_URL2 for audio
        if mode == "audio" and API_URL2:
            try:
                api_url2 = f"{API_URL2}?direct&id={video_id}"
                logger.info(f"Trying API_URL2: {api_url2}")
                async with session.get(api_url2, timeout=10) as response:
                    if response.status != 200:
                        raise Exception(f"API_URL2 failed with status {response.status}")
                    async with session.get(await response.text(), timeout=30) as dl_response:
                        if dl_response.status != 200:
                            raise Exception(f"Download failed with status {dl_response.status}")
                        with open(file_path, 'wb') as f:
                            while True:
                                chunk = await dl_response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        logger.info(f"Downloaded {file_path} via API_URL2")
                        return file_path
            except Exception as e:
                logger.error(f"API_URL2 failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    logger.error(f"All API attempts failed for {video_id}")
    return None

def cookie_txt_file():
    """
    Returns a random cookies file from the cookies directory or the default cookies.txt.
    """
    cookie_dir = "cookies"
    default_cookie = os.path.join(cookie_dir, "cookies.txt")
    
    if os.path.exists(default_cookie):
        logger.info(f"Using default cookies file: {default_cookie}")
        return default_cookie
    
    try:
        cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
        if cookies_files:
            cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
            logger.info(f"Using random cookies file: {cookie_file}")
            return cookie_file
        raise FileNotFoundError("No cookies files found in directory")
    except Exception as e:
        logger.error(f"Error accessing cookies: {e}")
        raise FileNotFoundError(f"Cookies file not found: {e}")

async def check_file_size(link):
    """
    Checks the file size of a YouTube video using yt-dlp.
    """
    async def get_format_info(link):
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--cookies", cookie_txt_file(),
                "--no-warnings",
                "-J",
                link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f'yt-dlp error: {stderr.decode()}')
                return None
            return json.loads(stdout.decode())
        except Exception as e:
            logger.error(f"Exception in get_format_info: {e}")
            return None

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format and format['filesize']:
                total_size += format['filesize']
            elif 'filesize_approx' in format and format['filesize_approx']:
                total_size += format['filesize_approx']
        return total_size if total_size > 0 else None

    info = await get_format_info(link)
    if not info:
        logger.error("Failed to retrieve format info")
        return None
    
    formats = info.get('formats', [])
    if not formats:
        logger.error("No formats found")
        return None
    
    total_size = parse_size(formats)
    if not total_size:
        logger.error("No valid file size found")
        return None
    
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        error_text = errorz.decode("utf-8").lower()
        if "unavailable videos are hidden" in error_text:
            return out.decode("utf-8")
        logger.error(f"Shell command error: {error_text}")
        return error_text
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        result = (await results.next())["result"][0]
        title = result["title"]
        duration_min = result["duration"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min and duration_min != "None" else 0
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        return (await results.next())["result"][0]["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        return (await results.next())["result"][0]["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        return (await results.next())["result"][0]["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        result = [key for key in playlist.split("\n") if key]
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        result = (await results.next())["result"][0]
        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, result["id"]

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                if "dash" in str(format.get("format", "")).lower():
                    continue
                if all(key in format for key in ["format", "filesize", "format_id", "ext", "format_note"]):
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format["filesize"],
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format["format_note"],
                        "yturl": link,
                    })
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result", [])[query_type]
        return (
            result["title"],
            result["duration"],
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"]
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> tuple[str, bool]:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            video_id = extract_video_id(link)
            path = api_dl(video_id, mode="audio")
            if path:
                return path
            
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    logger.info(f"File {xyz} already exists")
                    return xyz
                x.download([link])
                logger.info(f"Downloaded audio to {xyz}")
                return xyz

        def video_dl():
            video_id = extract_video_id(link)
            path = api_dl(video_id, mode="video")
            if path:
                return path
            
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    logger.info(f"File {xyz} already exists")
                    return xyz
                x.download([link])
                logger.info(f"Downloaded video to {xyz}")
                return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}.mp4"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                x.download([link])
                logger.info(f"Downloaded song video to {fpath}")
                return fpath

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as x:
                x.download([link])
                logger.info(f"Downloaded song audio to {fpath % {'ext': 'mp3'}}")
                return fpath % {'ext': 'mp3'}

        try:
            if songvideo:
                downloaded_file = await loop.run_in_executor(None, song_video_dl)
                return downloaded_file, True
            elif songaudio:
                downloaded_file = await loop.run_in_executor(None, song_audio_dl)
                return downloaded_file, True
            elif video:
                if await is_on_off(1):
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    return downloaded_file, True
                else:
                    proc = await asyncio.create_subprocess_exec(
                        "yt-dlp",
                        "--cookies", cookie_txt_file(),
                        "-g",
                        "-f",
                        "best[height<=?720][width<=?1280]",
                        link,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await proc.communicate()
                    if stdout:
                        downloaded_file = stdout.decode().split("\n")[0]
                        return downloaded_file, False
                    else:
                        file_size = await check_file_size(link)
                        if not file_size:
                            logger.error("Failed to retrieve file size")
                            return None, False
                        total_size_mb = file_size / (1024 * 1024)
                        if total_size_mb > 250:
                            logger.error(f"File size {total_size_mb:.2f} MB exceeds 250MB limit")
                            return None, False
                        downloaded_file = await loop.run_in_executor(None, video_dl)
                        return downloaded_file, True
            else:
                downloaded_file = await loop.run_in_executor(None, audio_dl)
                return downloaded_file, True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, False
