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

    async def valid(self, link: str):
        if "soundcloud.com" in link:
            return True
        return False

    async def download(self, url):
        d = YoutubeDL(self.opts)
        try:
            info = d.extract_info(url, download=True)
        except Exception as e:
            print(f"Download failed: {e}")
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
