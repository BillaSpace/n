import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch
import config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpotifyAPI:
    def __init__(self):
        # Updated regex to handle Spotify URLs
        self.regex = r"^https:\/\/open\.spotify\.com\/[a-z]{2}\/(track|playlist|album|artist)\/[a-zA-Z0-9\-._/?=&%]+"
        cid = config.SPOTIFY_CLIENT_ID
        secret = config.SPOTIFY_CLIENT_SECRET
        if cid and secret:
            auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
            self.spotify = spotipy.Spotify(auth_manager=auth)
        else:
            self.spotify = None

    def valid(self, link: str) -> bool:
        """Check if the URL is a valid Spotify URL."""
        logger.info(f"Validating Spotify URL: {link}")
        return bool(re.match(self.regex, link))

    def safe_spotify_call(self, method, *args, retries=3, delay=5):
        """Safely call Spotify API with retries."""
        for attempt in range(retries):
            try:
                return method(*args)
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Spotify API call failed after {retries} attempts: {str(e)}")
                    raise e
                logger.warning(f"Spotify API call failed, retrying... ({attempt + 1}/{retries}): {str(e)}")
                import time
                time.sleep(delay)

    def get_track_info(self, link: str) -> dict:
        """Fetch Spotify track and convert to YouTube."""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")
        track = self.safe_spotify_call(self.spotify.track, link)
        query = track["name"] + "".join(
            f" {a['name']}" for a in track["artists"] if a["name"] != "Various Artists"
        )
        logger.info(f"Searching YouTube for query: {query}")
        results = VideosSearch(query, limit=1)
        data = results.next()
        result = data["result"][0]
        return {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }

    def track(self, link: str):
        """Fetch details for a Spotify track."""
        track_info = self.get_track_info(link)
        return track_info, track_info["vidid"]

    def playlist(self, url: str):
        """Fetch Spotify playlist with track limit."""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")
        playlist = self.safe_spotify_call(self.spotify.playlist, url)
        playlist_id = playlist["id"]
        results = playlist["tracks"]["items"]
        next_page = playlist["tracks"]["next"]
        track_limit = 150  # Limit to 150 tracks to avoid excessive API calls
        current_count = len(results)
        while next_page and current_count < track_limit:
            next_tracks = self.safe_spotify_call(self.spotify.next, playlist["tracks"])
            results.extend(next_tracks["items"][:track_limit - current_count])
            playlist["tracks"] = next_tracks
            next_page = next_tracks.get("next")
            current_count = len(results)
        titles = []
        for item in results:
            track = item.get("track")
            if not track:
                continue
            name = track["name"]
            artists = " ".join(
                a["name"] for a in track["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")
        return titles, playlist_id

    def album(self, url: str):
        """Fetch Spotify album with track limit."""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")
        album = self.safe_spotify_call(self.spotify.album, url)
        album_id = album["id"]
        results = album["tracks"]["items"]
        next_page = album["tracks"].get("next")
        track_limit = 50  # Limit to 50 tracks
        current_count = len(results)
        while next_page and current_count < track_limit:
            next_tracks = self.safe_spotify_call(self.spotify.next, album["tracks"])
            results.extend(next_tracks["items"][:track_limit - current_count])
            album["tracks"] = next_tracks
            next_page = next_tracks.get("next")
            current_count = len(results)
        titles = []
        for item in results:
            name = item["name"]
            artists = " ".join(
                a["name"] for a in item["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")
        return titles, album_id

    def artist(self, url: str):
        """Fetch Spotify artist top tracks."""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")
        artist = self.safe_spotify_call(self.spotify.artist, url)
        artist_id = artist["id"]
        top_tracks_data = self.safe_spotify_call(
            self.spotify.artist_top_tracks, artist_id
        )
        top_tracks = top_tracks_data["tracks"]
        titles = []
        for track in top_tracks:
            name = track["name"]
            artists = " ".join(
                a["name"] for a in track["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")
        return titles, artist_id
