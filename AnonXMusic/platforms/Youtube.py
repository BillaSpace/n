import asyncio
import os
import re
import json
from typing import Union
import aiohttp
from yt_dlp import YoutubeDL
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds
import glob
import random
from config import API_URL1, API_URL2

def extract_video_id(link: str) -> str:
    """Extracts the video ID from YouTube or YouTube Music URLs."""
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
    raise ValueError("Invalid YouTube or YouTube Music link provided.")

async def api_dl(video_id: str, mode: str = "audio") -> str:
    """Downloads audio or video using API_URL1 or API_URL2."""
    file_ext = "mp3" if mode == "audio" else "mp4"
    file_path = os.path.join("downloads", f"{video_id}.{file_ext}")
    if os.path.exists(file_path):
        return file_path

    async with aiohttp.ClientSession() as session:
        if API_URL1:
            try:
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                api_url1 = f"{API_URL1}{youtube_url}&downloadMode={mode}"
                async with session.get(api_url1) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("successful") == "success" and "url" in data.get("data", {}):
                            download_url = data["data"]["url"]
                            os.makedirs("downloads", exist_ok=True)
                            async with session.get(download_url) as dl_response:
                                if dl_response.status == 200:
                                    with open(file_path, 'wb') as f:
                                        async for chunk in dl_response.content.iter_chunked(8192):
                                            f.write(chunk)
                                    return file_path
            except Exception:
                pass

        if mode == "audio" and API_URL2:
            try:
                api_url2 = f"{API_URL2}?direct&id={video_id}"
                async with session.get(api_url2) as response:
                    if response.status == 200:
                        os.makedirs("downloads", exist_ok=True)
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        return file_path
            except Exception:
                if os.path.exists(file_path):
                    os.remove(file_path)
    return None

def cookie_txt_file():
    """Selects a random cookie file for yt-dlp."""
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    return f"cookies/{random.choice(txt_files).split('/')[-1]}"

async def check_file_size(link):
    """Checks file size using yt-dlp."""
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    formats = info.get('formats', [])
    if not formats:
        return None
    return parse_size(formats)

async def shell_cmd(cmd):
    """Executes shell commands for yt-dlp."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz and "unavailable videos are hidden" not in errorz.decode("utf-8").lower():
        return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.semaphore = asyncio.Semaphore(5)  # Limit metadata operations
        self.dl_semaphore = asyncio.Semaphore(3)  # Limit downloads

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message: Message) -> Union[str, None]:
        messages = [message]
        if message.reply_to_message:
            messages.append(message.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return text[offset : offset + length] if offset is not None else None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            results = await asyncio.to_thread(VideosSearch, link, limit=1)
            result = (await results.next())["result"][0]
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
            return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            results = await asyncio.to_thread(VideosSearch, link, limit=1)
            result = (await results.next())["result"][0]
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            results = await asyncio.to_thread(VideosSearch, link, limit=1)
            result = (await results.next())["result"][0]
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            results = await asyncio.to_thread(VideosSearch, link, limit=1)
            result = (await results.next())["result"][0]
            return result["thumbnails"][0]["url"].split("?")[0]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            results = await asyncio.to_thread(VideosSearch, link, limit=1)
            result = (await results.next())["result"][0]
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }
            return track_details, result["id"]

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.listbase + link
            if "&" in link:
                link = link.split("&")[0]
            cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {min(limit, 50)} --skip-download {link}"
            playlist = await shell_cmd(cmd)
            result = [key for key in playlist.split("\n") if key]
            return result

    async def video(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
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

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
            ydl = YoutubeDL(ytdl_opts)
            formats_available = []
            r = await asyncio.to_thread(ydl.extract_info, link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if "dash" not in str(format["format"]).lower():
                    try:
                        formats_available.append({
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        })
                    except:
                        continue
            return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        async with self.semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            a = await asyncio.to_thread(VideosSearch, link, limit=10)
            result = (await a.next()).get("result")
            title = result[query_type]["title"]
            duration_min = result[query_type]["duration"]
            vidid = result[query_type]["id"]
            thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
            return title, duration_min, thumbnail, vidid

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
    ) -> str:
        async with self.dl_semaphore:
            if videoid:
                link = self.base + link
            if "&" in link:
                link = link.split("&")[0]
            video_id = extract_video_id(link)

            async def dl(mode: str, ytdl_opts: dict = None):
                path = await api_dl(video_id, mode)
                if path:
                    return path
                ydl = YoutubeDL(ytdl_opts or {"quiet": True, "cookiefile": cookie_txt_file()})
                info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    return xyz
                await asyncio.to_thread(ydl.download, [link])
                return xyz

            if songvideo:
                ytdl_opts = {
                    "format": f"{format_id}+140",
                    "outtmpl": f"downloads/{title}.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "prefer_ffmpeg": True,
                    "merge_output_format": "mp4",
                }
                path = await dl("video", ytdl_opts)
                return f"downloads/{title}.mp4"
            elif songaudio:
                ytdl_opts = {
                    "format": format_id,
                    "outtmpl": f"downloads/{title}.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                    "prefer_ffmpeg": True,
                    "postprocessors": [
                        {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
                    ],
                }
                path = await dl("audio", ytdl_opts)
                return f"downloads/{title}.mp3"
            elif video:
                if await is_on_off(1):
                    return await dl("video", {
                        "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "cookiefile": cookie_txt_file(),
                    }), True
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
                        return stdout.decode().split("\n")[0], False
                    file_size = await check_file_size(link)
                    if not file_size or file_size / (1024 * 1024) > 250:
                        return None, False
                    return await dl("video", {
                        "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "cookiefile": cookie_txt_file(),
                    }), True
            else:
                return await dl("audio", {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "cookiefile": cookie_txt_file(),
                }), True
