import re
import json
from typing import Union, List, Dict

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppleAPI:
    def __init__(self):
        self.regex = r"^https:\/\/music\.apple\.com\/"
        self.base = "https://music.apple.com/in/playlist/"

    def valid(self, link: str) -> bool:
        """Check if the URL is a valid Apple Music URL."""
        logger.info(f"Validating Apple Music URL: {link}")
        return bool(re.match(self.regex, link))

    async def fetch_html(self, url: str) -> Union[str, None]:
        """Fetch HTML content from the given URL."""
        logger.info(f"Fetching HTML for URL: {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    logger.error(f"Failed to fetch URL {url}: Status {r.status}")
                    return None
                return await r.text()

    def map_yt_result(self, v: dict) -> dict:
        """Map YouTube search result to track details."""
        return {
            "title": v["title"],
            "link": v["link"],
            "vidid": v["id"],  # Match old apple.py's key
            "duration_min": v["duration"],  # Match old apple.py's key
            "thumb": v["thumbnails"][0]["url"].split("?")[0],
        }

    async def track(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[Dict, str], None]:
        """Fetch details for an Apple Music track."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed track URL: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for track URL: {url}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if not title_tag:
            logger.error("No <title> tag found in HTML")
            return None

        parts = title_tag.text.split(" - ")
        query = " ".join(parts[:2]).strip()
        logger.info(f"Searching YouTube for query: {query}")

        results = VideosSearch(query, limit=1)
        r = await results.next()
        if not r["result"]:
            logger.error(f"No YouTube results found for query: {query}")
            return None

        track_details = self.map_yt_result(r["result"][0])
        return track_details, track_details["vidid"]  # Return tuple to match old apple.py

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[List[Dict], str], None]:
        """Fetch details for an Apple Music playlist."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed playlist URL: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for playlist URL: {url}")
            return None

        try:
            playlist_id = url.split("playlist/")[1]
        except IndexError:
            logger.error(f"Invalid playlist URL format: {url}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        queries = []

        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(script.string)
                if "track" in data:
                    for track in data["track"]:
                        name = track.get("name")
                        artist = track.get("byArtist", {}).get("name")
                        if name and artist:
                            queries.append(f"{name} {artist}")
            except Exception as e:
                logger.warning(f"Error parsing JSON-LD: {str(e)}")
                continue

        if not queries:
            logger.error("No tracks found in playlist")
            return None

        results = []
        for query in queries:
            logger.info(f"Searching YouTube for playlist track: {query}")
            search = VideosSearch(query, limit=1)
            r = await search.next()
            if r["result"]:
                results.append(self.map_yt_result(r["result"][0]))

        if not results:
            logger.error("No YouTube results found for playlist tracks")
            return None

        return results, playlist_id  # Return tuple to match old apple.py
