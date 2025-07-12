import re
import json
from typing import Union, List, Dict

import requests
from bs4 import BeautifulSoup
from youtubesearchpython import VideosSearch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppleAPI:
    def __init__(self):
        # Updated regex to handle both existing and new Apple Music/iTunes URL formats
        self.regex = r"^https:\/\/(music|itunes)\.apple\.com\/[a-z]{2}\/(album|playlist|artist|song)\/[a-zA-Z0-9\-._/?=&%]+(\?i=[0-9]+&ls)?$"
        self.base = "https://music.apple.com/in/playlist/"

    def valid(self, link: str) -> bool:
        """Check if the URL is a valid Apple Music or iTunes URL."""
        logger.info(f"Validating URL: {link}")
        return bool(re.match(self.regex, link))

    def fetch_html(self, url: str) -> Union[str, None]:
        """Fetch HTML content from the given URL."""
        logger.info(f"Fetching HTML for URL: {url}")
        try:
            r = requests.get(url)
            if r.status_code != 200:
                logger.error(f"Failed to fetch URL {url}: Status {r.status_code}")
                return None
            return r.text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None

    def map_yt_result(self, v: dict) -> dict:
        """Map YouTube search result to track details."""
        return {
            "title": v["title"],
            "link": v["link"],
            "vidid": v["id"],  # Match old apple.py's key
            "duration_min": v["duration"],  # Match old apple.py's key
            "thumb": v["thumbnails"][0]["url"].split("?")[0],
        }

    def track(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[Dict, str], None]:
        """Fetch details for an Apple Music or iTunes track."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed track URL: {url}")

        html = self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for track URL: {url}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if not title_tag:
            logger.error("No <title> tag found in HTML")
            return None

        # Clean up the title to remove unwanted text (e.g., "Apple Music" or special characters)
        title_text = title_tag.text.replace("‎", "").replace(" – Apple Music", "").strip()
        parts = title_text.split(" – ")
        if len(parts) < 2:
            logger.error(f"Invalid title format: {title_text}")
            return None

        # Construct query from song title and artist (first two parts)
        query = " ".join(parts[:2]).strip()
        logger.info(f"Searching YouTube for query: {query}")

        results = VideosSearch(query, limit=1)
        r = results.next()  # Synchronous call
        if not r["result"]:
            logger.error(f"No YouTube results found for query: {query}")
            return None

        track_details = self.map_yt_result(r["result"][0])
        # Use track ID from URL if available, else fallback to YouTube video ID
        track_id = re.search(r"\?i=([0-9]+)", url)
        track_id = track_id.group(1) if track_id else track_details["vidid"]
        return track_details, track_id  # Return tuple to match old apple.py

    def playlist(self, url: str, playid: Union[bool, str] = None) -> Union[tuple[List[Dict], str], None]:
        """Fetch details for an Apple Music or iTunes playlist."""
        if playid:
            url = self.base + url
            logger.info(f"Constructed playlist URL: {url}")

        html = self.fetch_html(url)
        if not html:
            logger.error(f"No HTML content retrieved for playlist URL: {url}")
            return None

        try:
            # Handle both playlist formats (e.g., pl.<hex> or simple playlist name)
            playlist_id = url.split("playlist/")[1].split("?")[0] if "?" in url else url.split("playlist/")[1]
        except IndexError:
            logger.error(f"Invalid playlist URL format: {url}")
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
                    # Extract track name and artist from HTML
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
            search = VideosSearch(query, limit=1)
            r = search.next()  # Synchronous call
            if r["result"]:
                results.append(self.map_yt_result(r["result"][0]))
            else:
                logger.warning(f"No YouTube results found for query: {query}")

        if not results:
            logger.error("No YouTube results found for any playlist tracks")
            return None

        return results, playlist_id  # Return tuple to match old apple.py
