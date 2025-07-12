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
import logging
from config import API_URL1, API_URL2

# Configure logging
logging.basicConfig(
    filename="bot.log",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    logger.error(f"Invalid YouTube link: {link}")
    return None

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
                async with session.get(api_url1, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("successful") == "success" and "url" in data.get("data", {}):
                            download_url = data["data"]["url"]
                            os.makedirs("downloads", exist_ok=True)
                            async with session.get(download_url, timeout=60) as dl_response:
                                if dl_response.status == 200:
                                    with open(file_path, 'wb') as f:
                                        async for chunk in dl_response.content.iter_chunked(8192):
                                            f.write(chunk)
                                    return file_path
                        else:
                            logger.error(f"API_URL1 failed for {video_id}: {data}")
                    else:
                        logger.error(f"API_URL1 returned status {response.status} for {video_id}")
            except Exception as e:
                logger.error(f"API_URL1 error for {video_id}: {str(e)}")

        if mode == "audio" and API_URL2:
            try:
                api_url2 = f"{API_URL2}?direct&id={video_id}"
                async with session.get(api_url2, timeout=30) as response:
                    if response.status == 200:
                        os.makedirs("downloads", exist_ok=True)
                        with open(file_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        return file_path
                    else:
                        logger.error(f"API_URL2 returned status {response.status} for {video_id}")
            except Exception as e:
                logger.error(f"API_URL2 error for {video_id}: {str(e)}")
                if os.path.exists(file_path):
                    os.remove(file_path)
    return None

def cookie_txt_file():
    """Selects a random cookie file for yt-dlp."""
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        logger.error("No cookie files found in cookies/ directory")
        return None
    return f"cookies/{random.choice(txt_files).split('/')[-1]}"

async def check_file_size(link):
    """Checks file size using yt-dlp."""
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        cmd = ["yt-dlp", "-J", link]
        if cookie_file:
            cmd.insert(1, "--cookies")
            cmd.insert(2, cookie_file)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"yt-dlp failed for {link}: {stderr.decode()}")
                return None
            return json.loads(stdout.decode())
        except Exception as e:
            logger.error(f"yt-dlp error for {link}: {str(e)}")
            return None

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
        logger.error(f"No formats found for {link}")
        return None
    return parse_size(formats)

async def shell_cmd(cmd):
    """Executes shell commands for yt-dlp."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, errorz = await proc.communicate()
        if errorz and "unavailable videos are hidden" not in errorz.decode("utf-8").lower():
            logger.error(f"Shell command failed: {cmd}, Error: {errorz.decode()}")
            return errorz.decode("utf-8")
        return out.decode("utf-8")
    except Exception as e:
        logger.error(f"Shell command error: {cmd}, Exception: {str(e)}")
        return ""

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be|music\.youtube\.com)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.semaphore = asyncio.Semaphore(5)
        self.dl_semaphore = asyncio.Semaphore(3)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        try:
            if videoid:
                link = self.base + link
            return bool(re.search(self.regex, link))
        except Exception as e:
            logger.error(f"exists failed for {link}: {str(e)}")
            return False

    async def url(self, message: Message) -> Union[str, None]:
        try:
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
        except Exception as e:
            logger.error(f"url extraction failed: {str(e)}")
            return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
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
            except Exception as e:
                logger.error(f"details failed for {link}: {str(e)}")
                return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                results = await asyncio.to_thread(VideosSearch, link, limit=1)
                result = (await results.next())["result"][0]
                return result["title"]
            except Exception as e:
                logger.error(f"title failed for {link}: {str(e)}")
                return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                results = await asyncio.to_thread(VideosSearch, link, limit=1)
                result = (await results.next())["result"][0]
                return result["duration"]
            except Exception as e:
                logger.error(f"duration failed for {link}: {str(e)}")
                return None

    async def thumbnail(self, link: str, vidoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                results = await asyncio.to_thread(VideosSearch, link, limit=1)
                result = (await results.next())["result"][0]
                return result["thumbnails"][0]["url"].split("?")[0]
            except Exception as e:
                logger.error(f"thumbnail failed for {link}: {str(e)}")
                return None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
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
            except Exception as e:
                logger.error(f"track failed for {link}: {str(e)}")
                return None, None

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.listbase + link
                if "&" in link:
                    link = link.split("&")[0]
                cookie_file = cookie_txt_file()
                cmd = f"yt-dlp -i --get-id --flat-playlist --playlist-end {min(limit, 50)} --skip-download {link}"
                if cookie_file:
                    cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {min(limit, 50)} --skip-download {link}"
                playlist = await shell_cmd(cmd)
                result = [key for key in playlist.split("\n") if key]
                return result
            except Exception as e:
                logger.error(f"playlist failed for {link}: {str(e)}")
                return []

    async def video(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                cookie_file = cookie_txt_file()
                cmd = [
                    "yt-dlp",
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    link
                ]
                if cookie_file:
                    cmd.insert(1, "--cookies")
                    cmd.insert(2, cookie_file)
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return 1, stdout.decode().split("\n")[0]
                logger.error(f"video failed for {link}: {stderr.decode()}")
                return 0, stderr.decode()
            except Exception as e:
                logger.error(f"video failed for {link}: {str(e)}")
                return 0, str(e)

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                ytdl_opts = {"quiet": True}
                cookie_file = cookie_txt_file()
                if cookie_file:
                    ytdl_opts["cookiefile"] = cookie_file
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
            except Exception as e:
                logger.error(f"formats failed for {link}: {str(e)}")
                return [], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        async with self.semaphore:
            try:
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
            except Exception as e:
                logger.error(f"slider failed for {link}, query_type {query_type}: {str(e)}")
                return None, None, None, None

    async def search(self, query: str):
        async with self.semaphore:
            try:
                results = await asyncio.to_thread(VideosSearch, query, limit=1)
                result = (await results.next())["result"][0]
                track_details = {
                    "title": result["title"],
                    "link": result["link"],
                    "vidid": result["id"],
                    "duration_min": result["duration"],
                    "thumb": result["thumbnails"][0]["url"].split("?")[0],
                }
                return track_details, result["id"]
            except Exception as e:
                logger.error(f"search failed for query {query}: {str(e)}")
                return None, None

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
            try:
                if videoid:
                    link = self.base + link
                if "&" in link:
                    link = link.split("&")[0]
                video_id = extract_video_id(link)
                if not video_id:
                    logger.error(f"Invalid video ID for {link}")
                    return None, False

                async def dl(mode: str, ytdl_opts: dict = None):
                    path = await api_dl(video_id, mode)
                    if path and os.path.exists(path):
                        return path
                    ytdl_opts = ytdl_opts or {"quiet": True}
                    cookie_file = cookie_txt_file()
                    if cookie_file:
                        ytdl_opts["cookiefile"] = cookie_file
                    ydl = YoutubeDL(ytdl_opts)
                    try:
                        info = await asyncio.to_thread(ydl.extract_info, link, download=False)
                        xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                        if os.path.exists(xyz):
                            return xyz
                        await asyncio.to_thread(ydl.download, [link])
                        if os.path.exists(xyz):
                            return xyz
                        logger.error(f"Download failed for {link}: File {xyz} not found")
                        return None
                    except Exception as e:
                        logger.error(f"yt-dlp download failed for {link}: {str(e)}")
                        return None

                if songvideo:
                    ytdl_opts = {
                        "format": f"{format_id}+140",
                        "outtmpl": f"downloads/{title}.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "prefer_ffmpeg": True,
                        "merge_output_format": "mp4",
                    }
                    path = await dl("video", ytdl_opts)
                    return path, True if path else (None, True)
                elif songaudio:
                    ytdl_opts = {
                        "format": format_id or "bestaudio/best",
                        "outtmpl": f"downloads/{title}.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                        "prefer_ffmpeg": True,
                        "postprocessors": [
                            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
                        ],
                    }
                    path = await dl("audio", ytdl_opts)
                    return path, True if path else (None, True)
                elif video:
                    if await is_on_off(1):
                        ytdl_opts = {
                            "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                            "outtmpl": "downloads/%(id)s.%(ext)s",
                            "geo_bypass": True,
                            "nocheckcertificate": True,
                            "quiet": True,
                        }
                        path = await dl("video", ytdl_opts)
                        return path, True if path else (None, True)
                    else:
                        cookie_file = cookie_txt_file()
                        cmd = [
                            "yt-dlp",
                            "-g",
                            "-f",
                            "best[height<=?720][width<=?1280]",
                            link
                        ]
                        if cookie_file:
                            cmd.insert(1, "--cookies")
                            cmd.insert(2, cookie_file)
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await proc.communicate()
                        if stdout:
                            return stdout.decode().split("\n")[0], False
                        logger.error(f"Stream URL fetch failed for {link}: {stderr.decode()}")
                        file_size = await check_file_size(link)
                        if not file_size or file_size / (1024 * 1024) > 250:
                            logger.error(f"File size too large or unavailable for {link}")
                            return None, False
                        ytdl_opts = {
                            "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                            "outtmpl": "downloads/%(id)s.%(ext)s",
                            "geo_bypass": True,
                            "nocheckcertificate": True,
                            "quiet": True,
                        }
                        path = await dl("video", ytdl_opts)
                        return path, True if path else (None, True)
                else:
                    ytdl_opts = {
                        "format": "bestaudio/best",
                        "outtmpl": "downloads/%(id)s.%(ext)s",
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "quiet": True,
                    }
                    path = await dl("audio", ytdl_opts)
                    return path, True if path else (None, True)
            except Exception as e:
                logger.error(f"download failed for {link}: {str(e)}")
                return None, False
