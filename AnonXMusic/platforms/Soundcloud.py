import asyncio
from os import path
from yt_dlp import YoutubeDL
from AnonXMusic.utils.formatters import seconds_to_min

class SoundAPI:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "format": "bestaudio/best",
            "retries": 3,
            "nooverwrites": False,
            "continuedl": True,
            "quiet": True,
        }
        self.semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent downloads

    async def valid(self, link: str):
        return "soundcloud.com" in link

    async def download(self, url):
        async with self.semaphore:
            d = YoutubeDL(self.opts)
            try:
                # Run yt_dlp in a thread to prevent blocking
                info = await asyncio.to_thread(d.extract_info, url, download=True)
            except Exception:
                return False
            xyz = path.join("downloads", f"{info['id']}.{info['ext']}")
            duration_min = seconds_to_min(info["duration"])
            track_details = {
                "title": info["title"],
                "duration_sec": info["duration"],
                "duration_min": duration_min,
                "uploader": info["uploader"],
                "filepath": xyz,
            }
            return track_details, xyz
