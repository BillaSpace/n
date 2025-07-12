import re
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.__future__ import VideosSearch
import config

class SpotifyAPI:
    def __init__(self):
        self.regex = r"^https:\/\/open\.spotify\.com\/"
        cid = config.SPOTIFY_CLIENT_ID
        secret = config.SPOTIFY_CLIENT_SECRET
        self.semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        if cid and secret:
            auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
            self.spotify = spotipy.Spotify(auth_manager=auth)
        else:
            self.spotify = None

    async def valid(self, link: str) -> bool:
        return bool(re.match(self.regex, link))

    async def safe_spotify_call(self, method, *args, retries=3, delay=5):
        """Safely call Spotify API with retries."""
        for attempt in range(retries):
            try:
                return await asyncio.to_thread(method, *args)
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(delay)

    async def get_track_info(self, link: str) -> dict:
        """Fetch Spotify track and convert to YouTube."""
        async with self.semaphore:
            if not self.spotify:
                raise Exception("Spotify client not initialized.")
            track = await self.safe_spotify_call(self.spotify.track, link)
            query = track["name"] + "".join(
                f" {a['name']}" for a in track["artists"] if a["name"] != "Various Artists"
            )
            # Run YouTube search in a thread to prevent blocking
            results = await asyncio.to_thread(VideosSearch, query, limit=1)
            data = await results.next()
            result = data["result"][0]
            return {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }

    async def track(self, link: str):
        track_info = await self.get_track_info(link)
        return track_info, track_info["vidid"]

    async def playlist(self, url: str):
        """Fetch Spotify playlist with track limit."""
        async with self.semaphore:
            if not self.spotify:
                raise Exception("Spotify client not initialized.")
            playlist = await self.safe_spotify_call(self.spotify.playlist, url)
            playlist_id = playlist["id"]
            results = playlist["tracks"]["items"]
            next_page = playlist["tracks"]["next"]
            track_limit = 150  # Limit to 50 tracks to avoid excessive API calls
            current_count = len(results)
            while next_page and current_count < track_limit:
                next_tracks = await self.safe_spotify_call(self.spotify.next, playlist["tracks"])
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

    async def album(self, url: str):
        """Fetch Spotify album with track limit."""
        async with self.semaphore:
            if not self.spotify:
                raise Exception("Spotify client not initialized.")
            album = await self.safe_spotify_call(self.spotify.album, url)
            album_id = album["id"]
            results = album["tracks"]["items"]
            next_page = album["tracks"].get("next")
            track_limit = 50  # Limit to 50 tracks
            current_count = len(results)
            while next_page and current_count < track_limit:
                next_tracks = await self.safe_spotify_call(self.spotify.next, album["tracks"])
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

    async def artist(self, url: str):
        """Fetch Spotify artist top tracks."""
        async with self.semaphore:
            if not self.spotify:
                raise Exception("Spotify client not initialized.")
            artist = await self.safe_spotify_call(self.spotify.artist, url)
            artist_id = artist["id"]
            top_tracks_data = await self.safe_spotify_call(
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
