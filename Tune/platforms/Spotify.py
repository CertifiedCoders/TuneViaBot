# Authored By Certified Coders © 2025
import re

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.aio import VideosSearch

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = re.compile(r"^https://open\.spotify\.com/.+")
        client_id = config.SPOTIFY_CLIENT_ID
        client_secret = config.SPOTIFY_CLIENT_SECRET
        if client_id and client_secret:
            credentials = SpotifyClientCredentials(client_id, client_secret)
            self.spotify = spotipy.Spotify(client_credentials_manager=credentials)
        else:
            self.spotify = None

    def _build_query(self, track_name: str, artists: list) -> str:
        query = track_name
        for artist in artists:
            name = artist["name"]
            if name != "Various Artists":
                query += f" {name}"
        return query

    def _require_spotify(self):
        if not self.spotify:
            raise RuntimeError("Spotify credentials not configured")

    async def valid(self, link: str) -> bool:
        return bool(self.regex.search(link or ""))

    async def track(self, link: str):
        self._require_spotify()
        track = self.spotify.track(link)
        query = self._build_query(track["name"], track["artists"])
        results = VideosSearch(query, limit=1)
        data = await results.next()
        r = data["result"][0]
        return {
            "title": r["title"],
            "link": r["link"],
            "vidid": r["id"],
            "duration_min": r["duration"],
            "thumb": r["thumbnails"][0]["url"].split("?")[0],
        }, r["id"]

    async def playlist(self, url):
        self._require_spotify()
        playlist = self.spotify.playlist(url)
        results = [
            self._build_query(item["track"]["name"], item["track"]["artists"])
            for item in playlist["tracks"]["items"]
            if item.get("track")
        ]
        return results, playlist["id"]

    async def album(self, url):
        self._require_spotify()
        album = self.spotify.album(url)
        results = [
            self._build_query(item["name"], item["artists"])
            for item in album["tracks"]["items"]
        ]
        return results, album["id"]

    async def artist(self, url):
        self._require_spotify()
        artist = self.spotify.artist(url)
        tracks = self.spotify.artist_top_tracks(url)
        results = [
            self._build_query(item["name"], item["artists"])
            for item in tracks["tracks"]
        ]
        return results, artist["id"]
