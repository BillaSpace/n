import re
import json
from typing import Union, List, Dict

import aiohttp
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch


class AppleAPI:
    def __init__(self):
        self.regex = r"^https:\/\/music\.apple\.com\/"

    def valid(self, link: str) -> bool:
        return bool(re.match(self.regex, link))

    async def fetch_html(self, url: str) -> Union[str, None]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                return await r.text()

    def map_yt_result(self, v: dict) -> dict:
        return {
            "title": v["title"],
            "link": v["link"],
            "id": v["id"],
            "duration": v["duration"],
            "thumb": v["thumbnails"][0]["url"].split("?")[0],
        }

    async def track(self, url: str) -> Union[Dict, None]:
        html = await self.fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if not title_tag:
            return None

        parts = title_tag.text.split(" - ")
        query = " ".join(parts[:2]).strip()

        results = VideosSearch(query, limit=1)
        r = await results.next()
        if not r["result"]:
            return None

        return self.map_yt_result(r["result"][0])

    def extract_playlist(self, html: str) -> List[str]:
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
            except Exception:
                continue

        return queries

    async def playlist(self, url: str) -> Union[List[dict], None]:
        html = await self.fetch_html(url)
        if not html:
            return None

        queries = self.extract_playlist(html)
        if not queries:
            return []

        results = []
        for query in queries:
            search = VideosSearch(query, limit=1)
            r = await search.next()
            if r["result"]:
                results.append(self.map_yt_result(r["result"][0]))

        return results
