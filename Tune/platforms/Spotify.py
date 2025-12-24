# Authored By Certified Coders © 2025
import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.aio import VideosSearch

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^https://open\.spotify\.com/.+"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        if self.client_id and self.client_secret:
            self.client_credentials_manager = SpotifyClientCredentials(
                self.client_id, self.client_secret
            )
            self.spotify = spotipy.Spotify(
                client_credentials_manager=self.client_credentials_manager
            )
        else:
            self.spotify = None

    def _build_track_query(self, track_name: str, artists: list) -> str:
        query = track_name
        for artist in artists:
            artist_name = f' {artist["name"]}'
            if "Various Artists" not in artist_name:
                query += artist_name
        return query

    async def valid(self, link: str) -> bool:
        return bool(re.search(self.regex, link or ""))

    async def track(self, link: str):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        track = self.spotify.track(link)
        query = self._build_track_query(track["name"], track["artists"])
        results = VideosSearch(query, limit=1)
        data = await results.next()
        r = data["result"][0]
        track_details = {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r["duration"],
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, track_details["vidid"]

    async def playlist(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        playlist = self.spotify.playlist(url)
        playlist_id = playlist["id"]
        results = []
        for item in playlist["tracks"]["items"]:
            music_track = item.get("track")
            if not music_track:
                continue
            query = self._build_track_query(music_track["name"], music_track["artists"])
            results.append(query)
        return results, playlist_id

    async def album(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        album = self.spotify.album(url)
        album_id = album["id"]
        results = []
        for item in album["tracks"]["items"]:
            query = self._build_track_query(item["name"], item["artists"])
            results.append(query)
        return results, album_id

    async def artist(self, url):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")
        artistinfo = self.spotify.artist(url)
        artist_id = artistinfo["id"]
        results = []
        artisttoptracks = self.spotify.artist_top_tracks(url)
        for item in artisttoptracks["tracks"]:
            query = self._build_track_query(item["name"], item["artists"])
            results.append(query)
        return results, artist_id
