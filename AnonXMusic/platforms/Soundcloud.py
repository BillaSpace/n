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

    async def valid(self, link: str) -> bool:
        return "soundcloud.com" in link

    async def download(self, url: str):
        d = YoutubeDL(self.opts)
        try:
            info = d.extract_info(url, download=True)
        except Exception as e:
            print(f"Download failed: {e}")
            return False

        file_path = path.join("downloads", f"{info.get('id')}.{info.get('ext')}")
        duration_sec = info.get("duration", 0)
        duration_min = seconds_to_min(duration_sec)

        track_details = {
            "title": info.get("title", "Unknown Title"),
            "duration_sec": duration_sec,
            "duration_min": duration_min,
            "uploader": info.get("uploader", "Unknown Uploader"),
            "filepath": file_path,
            "thumbnail": info.get("thumbnail"),  # Optional
        }
        return track_details, file_path           "filepath": xyz,
        }
        return track_details, xyz
