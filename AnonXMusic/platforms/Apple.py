import re
import logging
from typing import Union

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch

from config import APPLE_MUSIC_URL

logger = logging.getLogger(__name__)

class AppleAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/music.apple.com\/)(.*)$"
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str):
        return bool(re.search(self.regex, link))

    async def track(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url
        logger.info(f"Validating URL: {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch html Apple Track page. Status code: {response.status}")
                    return False
                html = await response.text()
        logger.info(f"Fetching HTML for apple track URL: {url}")
        soup = BeautifulSoup(html, "html.parser")

        search = None
        for tag in soup.find_all("meta"):
            if tag.get("property") == "og:title":
                search = tag.get("content")
                break

        if not search:
            logger.warning("og:title meta title query not found on youtube.")
            return False

        logger.info(f"Searching YouTube for query: {search} on Apple Music")
        results = VideosSearch(search, limit=1)
        data = await results.next()

        if not data["result"]:
            logger.warning("No YouTube results found.")
            return False

        result = data["result"][0]
        track_details = {
            "title": result.get("title"),
            "link": result.get("link"),
            "vidid": result.get("id"),
            "duration_min": result.get("duration"),
            "thumb": result.get("thumbnails", [{}])[0].get("url", APPLE_MUSIC_URL).split("?")[0]
                     if result.get("thumbnails") else APPLE_MUSIC_URL
        }

        return track_details, track_details["vidid"]

    async def playlist(self, url, playid: Union[bool, str] = None):
        if playid:
            url = self.base + url

        playlist_id = url.split("playlist/")[1]
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        applelinks = soup.find_all("meta", attrs={"property": "music:song"})
        results = []

        for item in applelinks:
            try:
                content = item["content"]
                title_part = ((content.split("album/")[1]).split("/")[0]).replace("-", " ")
                results.append(title_part)
            except Exception as e:
                logger.warning(f"Error parsing playlist item: {e}")
                continue

        return results, playlist_id
