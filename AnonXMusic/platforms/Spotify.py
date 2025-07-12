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
        """Fetch Spotify track and convert to YouTube"""
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        track = await asyncio.to_thread(self.spotify.track, link)

        query = track["name"] + "".join(
            f" {a['name']}" for a in track["artists"] if a["name"] != "Various Artists"
        )

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
        track_info = await self.get_track_info(link)
        return track_info, track_info["vidid"]

    async def playlist(self, url: str):
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        playlist = await asyncio.to_thread(self.spotify.playlist, url)
        playlist_id = playlist["id"]

        results = playlist["tracks"]["items"]
        next_page = playlist["tracks"]["next"]

        while next_page:
            next_tracks = await asyncio.to_thread(self.spotify.next, playlist["tracks"])
            results.extend(next_tracks["items"])
            playlist["tracks"] = next_tracks
            next_page = next_tracks.get("next")

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
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        album = await asyncio.to_thread(self.spotify.album, url)
        album_id = album["id"]

        results = album["tracks"]["items"]
        next_page = album["tracks"].get("next")

        while next_page:
            next_tracks = await asyncio.to_thread(self.spotify.next, album["tracks"])
            results.extend(next_tracks["items"])
            album["tracks"] = next_tracks
            next_page = next_tracks.get("next")

        titles = []
        for item in results:
            name = item["name"]
            artists = " ".join(
                a["name"] for a in item["artists"] if a["name"] != "Various Artists"
            )
            titles.append(f"{name} {artists}")

        return titles, album_id

    async def artist(self, url: str):
        if not self.spotify:
            raise Exception("Spotify client not initialized.")

        artist = await asyncio.to_thread(self.spotify.artist, url)
        artist_id = artist["id"]

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
        
