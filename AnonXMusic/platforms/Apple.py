import re
import json
from typing import Union, List, Dict
import unicodedata
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from youtubesearchpython.__future__ import VideosSearch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppleAPI:
    def __init__(self):
        # Updated regex to handle both Apple Music and iTunes URL formats
        self.regex = r"^https:\/\/(music|itunes)\.apple\.com\/[a-z]{2}\/(album|playlist|artist|song)\/[a-zA-Z0-9\-._/?=&%]+(\?i=[0-9]+&ls)?$"
        self.base = "https://music.apple.com/in/playlist/"

    async def valid(self, link: str) -> bool:
        """Check if the URL is a valid Apple Music or iTunes URL."""
        logger.info(f"Validating URL: {link}")
        return bool(re.match(self.regex, link))

    async def fetch_html(self, url: str) -> Union[str, None]:
        """Fetch HTML content from the given URL asynchronously."""
        logger.info(f"Fetching HTML for URL: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch URL {url}: Status {response.status}")
                        return None
                    return await response.text()
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None

    def map_yt_result(self, v: dict) -> dict:
        """Map YouTube search result to track details."""
        try:
            return {
                "title": v.get("title", ""),
                "link": v.get("link", ""),
                "vidid": v.get("id", ""),
                "duration_min": v.get("duration", ""),
                "thumb": v.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            }
        except Exception as e:
            logger.error(f"Error mapping YouTube result: {str(e)}")
            return {}

    async def track(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[Dict, str], None]:
        """Fetch details for an Apple Music or iTunes track asynchronously."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed track URL: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for track URL: {url}")
            return None

        soup = BeautifulSoup(html, "html.parser")

        # Try og:title meta tag first
        search = None
        for tag in soup.find_all("meta"):
            if tag.get("property", None) == "og:title":
                search = tag.get("content", None)
                break

        # Fallback to <title> tag with improved parsing
        if not search:
            title_tag = soup.find("title")
            if not title_tag:
                logger.error("No <title> tag found in HTML")
                return None

            # Normalize Unicode characters and clean title
            title_text = unicodedata.normalize("NFKD", title_tag.text).replace("‎", "").replace(" – Apple Music", "").strip()
            if " – Song by " in title_text:
                parts = title_text.split(" – Song by ")
                if len(parts) < 2:
                    logger.error(f"Invalid title format: {title_text}")
                    return None
                song = parts[0].strip()
                artists = parts[1].split(" – ")[0].strip()
                search = f"{song} {artists}"
            else:
                parts = title_text.split(" – ")
                if len(parts) < 2:
                    logger.error(f"Invalid title format: {title_text}")
                    return None
                search = " ".join(parts[:2]).strip()

        # Clean up search query
        search = search.replace(" on Apple Music", "").strip()
        logger.info(f"Searching YouTube for query: {search}")

        try:
            results = VideosSearch(search, limit=1)
            r = await asyncio.wait_for(results.next(), timeout=30.0)  # 30-second timeout
            if not r.get("result"):
                logger.error(f"No YouTube results found for query: {search}")
                return None
            track_details = self.map_yt_result(r["result"][0])
            if not track_details:
                logger.error(f"Failed to map YouTube result for query: {search}")
                return None
            track_id = re.search(r"\?i=([0-9]+)", url)
            track_id = track_id.group(1) if track_id else track_details["vidid"]
            return track_details, track_id
        except asyncio.TimeoutError:
            logger.error(f"YouTube search timed out for query: {search}")
            return None
        except Exception as e:
            logger.error(f"Error processing YouTube search for {url}: {str(e)}")
            return None

    async def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[List[Dict], str], None]:
        """Fetch details for an Apple Music or iTunes playlist asynchronously."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed playlist URL: {url}")

        html = await self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for playlist URL: {url}")
            return None

        # Improved playlist ID extraction with regex
        try:
            # Match playlist ID (hex or name) after 'playlist/'
            playlist_id_match = re.search(r"playlist/([a-zA-Z0-9\-._]+?)(?:[/?#]|$)", url)
            if not playlist_id_match:
                logger.error(f"Invalid playlist URL format: {url}")
                return None
            playlist_id = playlist_id_match.group(1)

            # Validate if it's a hex playlist ID (e.g., pl.<hex>)
            if playlist_id.startswith("pl."):
                hex_id = playlist_id[3:]  # Remove 'pl.' prefix
                if not re.match(r"^[0-9a-fA-F]{16,}$", hex_id):  # Require at least 16 chars for hex
                    logger.error(f"Invalid hexadecimal playlist ID: {hex_id}")
                    return None
                logger.info(f"Extracted hexadecimal playlist ID: {playlist_id}")
            else:
                # Validate non-hex playlist name
                if not re.match(r"^[a-zA-Z0-9\-._]{1,100}$", playlist_id):  # Limit length for safety
                    logger.error(f"Invalid playlist name format: {playlist_id}")
                    return None
                logger.info(f"Extracted playlist name: {playlist_id}")

        except Exception as e:
            logger.error(f"Error extracting playlist ID from URL {url}: {str(e)}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        queries = []

        # Try JSON-LD first
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

        # Fallback to scraping track list from HTML if JSON-LD yields no results
        if not queries:
            logger.info("No tracks found in JSON-LD, attempting HTML scraping")
            track_elements = soup.find_all("div", class_="songs-list-row")
            for track_elem in track_elements:
                try:
                    track_name_elem = track_elem.find("div", class_="songs-list-row__song-name")
                    artist_elem = track_elem.find("a", class_="songs-list-row__link")
                    if track_name_elem and artist_elem:
                        track_name = track_name_elem.text.strip()
                        artist_name = artist_elem.text.strip()
                        if track_name and artist_name:
                            queries.append(f"{track_name} {artist_name}")
                except Exception as e:
                    logger.warning(f"Error parsing track from HTML: {str(e)}")
                    continue

        if not queries:
            logger.error("No tracks found in playlist (both JSON-LD and HTML scraping failed)")
            return None

        results = []
        for query in queries:
            logger.info(f"Searching YouTube for playlist track: {query}")
            try:
                search = VideosSearch(query, limit=1)
                r = await asyncio.wait_for(search.next(), timeout=30.0)
                if r.get("result"):
                    track_details = self.map_yt_result(r["result"][0])
                    if track_details:
                        results.append(track_details)
                    else:
                        logger.warning(f"Failed to map YouTube result for query: {query}")
                else:
                    logger.warning(f"No YouTube results found for query: {query}")
            except asyncio.TimeoutError:
                logger.warning(f"YouTube search timed out for query: {query}")
                continue
            except Exception as e:
                logger.warning(f"Error searching YouTube for query {query}: {str(e)}")
                continue

        if not results:
            logger.error("No YouTube results found for any playlist tracks")
            return None

        return results, playlist_id
