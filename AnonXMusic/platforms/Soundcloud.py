import re
from os import path
from yt_dlp import YoutubeDL
from AnonXMusic.utils.formatters import seconds_to_min
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        self.regex = r"^https?://((www\.)?soundcloud\.com|on\.soundcloud\.com)/[a-zA-Z0-9\-._/?=&%]+"

    def valid(self, link: str) -> bool:
        """Check if the URL is a valid SoundCloud URL."""
        logger.info(f"Validating SoundCloud URL: {link}")
        return bool(re.match(self.regex, link))

    def download(self, url: str) -> tuple[dict, str] | bool:
        """Download audio from a SoundCloud URL and return track details."""
        logger.info(f"Downloading from URL: {url}")
        d = YoutubeDL(self.opts)
        try:
            info = d.extract_info(url, download=True)
        except Exception as e:
            logger.error(f"Failed to download from {url}: {str(e)}")
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
        return track_details, xyz  # Removed extra brace
