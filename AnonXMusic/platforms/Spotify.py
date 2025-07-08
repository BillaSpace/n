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
        if cid and secret:
            auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
            self.spotify = spotipy.Spotify(auth_manager=auth)
        else:
            self.spotify = None

    async def valid(self, link: str) -> bool:
        return bool(re.match(self.regex, link))

    async def get_track_info(self, link: str) -> dict:
        """Async helper function to fetch Spotify track and convert to YouTube"""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        # Spotify call in background thread
        track = await asyncio.to_thread(self.spotify.track, link)

        # Build search query
        query = track["name"] + "".join(
            f" {a['name']}" for a in track["artists"] if a["name"] != "Various Artists"
        )

        # YouTube Search
        results = VideosSearch(query, limit=1)
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
        """
        Main async method for external calls
        Returns (track_details_dict, video_id)
        """
        track_info = await self.get_track_info(link)
        return track_info, track_info["vidid"]

    async def playlist(self, url: str):
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        playlist_id = url.split("/")[-1].split("?")[0]

        results = await asyncio.to_thread(self.spotify.playlist_items, playlist_id)
        tracks = results["items"]

        while results.get("next"):
            results = await asyncio.to_thread(self.spotify.next, results)
            tracks.extend(results["items"])

        titles = []
        for item in tracks:
            track = item["track"]
            name = track["name"]
            artists = " ".join(
                a["name"] for a in track["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")

        return titles, playlist_id

    async def album(self, url: str):
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        album_id = url.split("/")[-1].split("?")[0]

        results = await asyncio.to_thread(self.spotify.album_tracks, album_id)
        tracks = results["items"]

        while results.get("next"):
            results = await asyncio.to_thread(self.spotify.next, results)
            tracks.extend(results["items"])

        titles = []
        for item in tracks:
            name = item["name"]
            artists = " ".join(
                a["name"] for a in item["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")

        return titles, album_id

    async def artist(self, url: str):
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        artist_id = url.split("/")[-1].split("?")[0]

        top_tracks_data = await asyncio.to_thread(
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
