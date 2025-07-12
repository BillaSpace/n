import re
import json
from typing import Union, List, Dict
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch

class AppleAPI:
    def __init__(self):
        self.regex = r"^https:\/\/music\.apple\.com\/"
        self.base = "https://music.apple.com/in/playlist/"
        self.semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests

    def valid(self, link: str) -> bool:
        """Check if the URL is a valid Apple Music URL."""
        return bool(re.match(self.regex, link))

    async def fetch_html(self, url: str) -> Union[str, None]:
        """Fetch HTML content from the given URL."""
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    if r.status != 200:
                        return None
                    return await r.text()

    def map_yt_result(self, v: dict) -> dict:
        """Map YouTube search result to track details."""
        return {
            "title": v["title"],
            "link": v["link"],
            "vidid": v["id"],
            "duration_min": v["duration"],
            "thumb": v["thumbnails"][0]["url"].split("?")[0],
        }

    async def track(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[Dict, str], None]:
        """Fetch details for an Apple Music track."""
        async with self.semaphore:
            if playid:
                url = self.base + url
            html = await self.fetch_html(url)
            if not html:
                return None
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            if not title_tag:
                return None
            parts = title_tag.text.split(" - ")
            query = " ".join(parts[:2]).strip()
            # Run YouTube search in a thread to prevent blocking
            search = await asyncio.to_thread(VideosSearch, query, limit=1)
            r = await search.next()
            if not r["result"]:
                return None
            track_details = self.map_yt_result(r["result"][0])
            return track_details, track_details["vidid"]

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[List[Dict], str], None]:
        """Fetch details for an Apple Music playlist."""
        async with self.semaphore:
            if playid:
                url = self.base + url
            try:
                playlist_id = url.split("playlist/")[1]
            except IndexError:
                return None
            html = await self.fetch_html(url)
            if not html:
                return None
            soup = BeautifulSoup(html, "html.parser")
            queries = []
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string)
                    if "track" in data:
                        for track in data["track"][:50]:  # Limit to 50 tracks
                            name = track.get("name")
                            artist = track.get("byArtist", {}).get("name")
                            if name and artist:
                                queries.append(f"{name} {artist}")
                except Exception:
                    continue
            if not queries:
                return None
            results = []
            for query in queries:
                search = await asyncio.to_thread(VideosSearch, query, limit=1)
                r = await search.next()
                if r["result"]:
                    results.append(self.map_yt_result(r["result"][0]))
            if not results:
                return None
            return results, playlist_id
