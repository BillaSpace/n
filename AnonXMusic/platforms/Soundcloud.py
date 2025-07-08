           "filepath": file_path,
            "thumbnail": info.get("thumbnail"),  # Optional
        }
        return track_details, file_path           "filepath": xyz,
        }
        return track_details, xyz
from os import path
from yt_dlp import YoutubeDL
from AnonXMusic.utils.formatters import seconds_to_min


class SoundAPI:
    def __init__(self):
        self.opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",       # Output path format
            "format": "bestaudio/best",                  # Best audio quality
            "retries": 3,                                # Retry count
            "nooverwrites": False,                       # Avoid overwriting files
            "continuedl": True,                          # Resume partial downloads
            "quiet": True,                               # Suppress verbose logging
        }

    async def valid(self, link: str) -> bool:
        """
        Validate whether the provided link is a SoundCloud link.
        """
        return "soundcloud.com" in link

    async def download(self, url: str):
        """
        Download a SoundCloud track using yt_dlp and return metadata.
        
        :param url: SoundCloud track URL
        :return: Tuple of (track_details dict, file path) or False on failure
        """
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
            "thumbnail": info.get("thumbnail"),  # Optional field
        }

        return track_details, file_path
