import asyncio
import os
import re
import json
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds

import logging
import requests
from config import API_URL1, API_URL2

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_video_id(link: str) -> str:
    """
    Extracts the video ID from a variety of YouTube and YouTube Music links.
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
    raise ValueError("Invalid YouTube or YouTube Music link provided.")

def api_dl(video_id: str, mode: str = "audio") -> str:
    """
    Downloads audio or video using API_URL1 (primary) or API_URL2 (fallback for audio).
    Returns the file path if successful, None otherwise.
    """
    file_ext = "mp3" if mode == "audio" else "mp4"
    file_path = os.path.join("downloads", f"{video_id}.{file_ext}")

    # Check if file already exists
    if os.path.exists(file_path):
        logger.info(f"{file_path} already exists. Skipping download.")
        return file_path

    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # Try API_URL1
    if API_URL1:
        try:
            # Fix URL construction to avoid double ?url=
            api_url1 = f"{API_URL1}?url={youtube_url}&downloadMode={mode}"
            logger.info(f"Trying API_URL1: {api_url1}")
            response = requests.get(api_url1, stream=True, timeout=30)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("successful") == "success" and "url" in data.get("data", {}):
                        download_url = data["data"]["url"]
                        os.makedirs("downloads", exist_ok=True)
                        with requests.get(download_url, stream=True, timeout=30) as dl_response:
                            if dl_response.status_code == 200:
                                with open(file_path, 'wb') as f:
                                    for chunk in dl_response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                logger.info(f"Downloaded {file_path} via API_URL1")
                                return file_path
                            else:
                                logger.error(f"Failed to download from API_URL1 URL: {download_url}. Status: {dl_response.status_code}")
                    else:
                        logger.error(f"API_URL1 invalid response for {video_id}: {data}")
                except ValueError as e:
                    logger.error(f"API_URL1 JSON decode error for {video_id}: {e}, Response: {response.text}")
            else:
                logger.error(f"API_URL1 request failed for {video_id}. Status: {response.status_code}, Response: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Error with API_URL1 for {video_id}: {e}")
    else:
        logger.warning("API_URL1 is not set. Skipping to API_URL2.")

    # Fallback to API_URL2 for audio only
    if mode == "audio" and API_URL2:
        try:
            api_url2 = f"{API_URL2}?direct&id={video_id}"
            logger.info(f"Trying API_URL2: {api_url2}")
            response = requests.get(api_url2, stream=True, timeout=30)
            if response.status_code == 200:
                os.makedirs("downloads", exist_ok=True)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Downloaded {file_path} via API_URL2")
                return file_path
            else:
                logger.error(f"API_URL2 failed for {video_id}. Status: {response.status_code}, Response: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Error with API_URL2 for {video_id}: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)

    logger.error(f"All APIs failed for {video_id}.")
    return None

def cookie_txt_file():
    """
    Returns the fixed path to the cookies file in Netscape format.
    """
    cookie_path = "cookies/cookies.txt"
    if not os.path.exists(cookie_path):
        logger.error(f"Cookies file not found at {cookie_path}")
        raise FileNotFoundError(f"Cookies file not found at {cookie_path}")
    logger.info(f"Using cookies file: {cookie_path}")
    return cookie_path

async def check_file_size(link):
    """
    Checks the file size of a YouTube video using yt-dlp.
    """
    async def get_format_info(link):
        try:
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
                logger.error(f'Error in get_format_info: {stderr.decode()}')
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
        logger.error("Failed to retrieve format info.")
        return None
    
    formats = info.get('formats', [])
    if not formats:
        logger.error("No formats found in info.")
        return None
    
    total_size = parse_size(formats)
    if not total_size:
        logger.error("No valid file size found in formats.")
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
        if "unavailable videos are hidden" in errorz.decode("utf-8").lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
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
        return text[offset:offset + length] if offset is not None else None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min =unofficial source code for AnonXMusic written in Python

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
        title = result["title"]
        duration_min = result["duration"]
        vidid = result["id"]
        yturl = result["link"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

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
                        "files.“

                        filesize": format["filesize"],
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
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            try:
                video_id = extract_video_id(link)
                path = api_dl(video_id, mode="audio")
                if path:
                    return path
                logger.error("APIs failed, falling back to cookies-based download")
            except Exception as e:
                logger.error(f"API download failed: {e}")

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
                    logger.info(f"File {xyz} already exists. Skipping download.")
                    return xyz
                x.download([link])
                logger.info(f"Downloaded audio to {xyz} using cookies-based method")
                return xyz

        def video_dl():
            try:
                video_id = extract_video_id(link)
                logger.info(f"Attempting to download video with ID: {video_id} using API_URL1")
                if not API_URL1:
                    logger.warning("API_URL1 is not set. Falling back to cookies-based download.")
                    raise ValueError("API_URL1 is not configured.")

                api_url1 = f"{API_URL1}?url={link}&downloadMode=video"
                logger.info(f"Requesting API_URL1: {api_url1}")
                response = requests.get(api_url1, stream=True, timeout=30)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.debug(f"API_URL1 response: {data}")
                        if data.get("successful") == "success" and "url" in data.get("data", {}):
                            download_url = data["data"]["url"]
                            logger.info(f"Download URL obtained: {download_url}")
                            os.makedirs("downloads", exist_ok=True)
                            file_path = os.path.join("downloads", f"{video_id}.mp4")
                            with requests.get(download_url, stream=True, timeout=30) as dl_response:
                                if dl_response.status_code == 200:
                                    with open(file_path, 'wb') as f:
                                        for chunk in dl_response.iter_content(chunk_size=8192):
                                            if chunk:
                                                f.write(chunk)
                                    logger.info(f"Successfully downloaded video to {file_path} via API_URL1")
                                    return file_path
                                else:
                                    logger.error(f"Failed to download from {download_url}. Status: {dl_response.status_code}")
                                    raise Exception(f"Download failed with status {dl_response.status_code}")
                        else:
                            logger.error(f"API_URL1 response invalid: {data}")
                            raise Exception("Invalid API_URL1 response")
                    except ValueError as e:
                        logger.error(f"API_URL1 JSON decode error: {e}, Response: {response.text}")
                        raise
                else:
                    logger.error(f"API_URL1 request failed. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"API_URL1 request failed with status {response.status_code}")
            except Exception as e:
                logger.error(f"API_URL1 video download failed: {e}")
                logger.info("Falling back to cookies-based download")

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
                    logger.info(f"File {xyz} already exists. Skipping download.")
                    return xyz
                x.download([link])
                logger.info(f"Downloaded video to {xyz} using cookies-based method")
                return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
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
                return f"downloads/{title}.mp4"

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
                return f"downloads/{title}.mp3"

        if songvideo:
            return await loop.run_in_executor(None, song_video_dl)
        elif songaudio:
            return await loop.run_in_executor(None, song_audio_dl)
        elif video:
            if await is_on_off(1):
                direct = True
                downloaded_file = await loop.run_in_executor(None, video_dl)
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
                    direct = False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        logger.error("Failed to retrieve file size.")
                        return None
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        logger.error(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit.")
                        return None
                    direct = True
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        return downloaded_file, direct
