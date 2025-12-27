# Authored By Certified Coders © 2025

from typing import List, Optional, Tuple, Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.aio import VideosSearch, Video, Playlist

from Tune.utils.downloader import yt_dlp_download, yt_dlp_get_stream_url, yt_dlp_get_playlist_ids
from Tune.utils.errors import capture_internal_err
from Tune.utils.tuning import (
    Track, LiveTrack, validate_youtube_url, extract_youtube_id,
    create_track_from_youtube_metadata, YOUTUBE_ID_RE
)


class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="

    async def _fetch_raw_metadata(self, query: Optional[str], url_type: str, video_id: Optional[str] = None, playlist_id: Optional[str] = None, url: Optional[str] = None) -> Optional[dict]:
        if url_type == "playlist":
            try:
                return await Playlist.get(f"{self.playlist_url}{playlist_id}")
            except Exception:
                return None
        
        if url_type == "video":
            if not video_id:
                return None
            try:
                video_url = url or f"{self.base_url}{video_id}"
                return await Video.get(video_url)
            except Exception:
                return None
        
        if url_type == "unknown" and query:
            try:
                results = (await VideosSearch(query, limit=1).next()).get("result", [])
                if results and (video_id := results[0].get("id")):
                    try:
                        return await Video.get(f"{self.base_url}{video_id}")
                    except Exception:
                        return results[0]
            except Exception:
                pass
        
        return None

    @capture_internal_err
    async def get_metadata(self, link: str, videoid: Union[str, bool, None] = None) -> Union[Track, LiveTrack, None]:
        if isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
            try:
                info = await Video.get(f"{self.base_url}{video_id}")
                if info:
                    return create_track_from_youtube_metadata(info, video_id, self.base_url)
            except Exception:
                pass
            return None
        
        url_type, video_id, playlist_id = validate_youtube_url(link)
        if url_type == "playlist":
            return None
        
        info = await self._fetch_raw_metadata(link if url_type == "unknown" else None, url_type, video_id, url=link if url_type == "video" else None)
        if not info:
            return None
        
        return create_track_from_youtube_metadata(info, video_id, self.base_url)

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        if videoid:
            return bool(YOUTUBE_ID_RE.match(str(videoid)))
        url_type, _, _ = validate_youtube_url(link)
        return url_type != "unknown"

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = (msg.entities or []) + (msg.caption_entities or [])
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    return text[ent.offset : ent.offset + ent.length].split("&si")[0]
                if ent.type == MessageEntityType.TEXT_LINK:
                    return ent.url.split("&si")[0]
        return None

    @capture_internal_err
    async def video(self, link: str = "", videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        video_id = None
        if isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
        elif link:
            url_type, video_id, _ = validate_youtube_url(link)
        
        if not video_id:
            return (0, "")
        
        url = f"{self.base_url}{video_id}"
        return await yt_dlp_get_stream_url(url)

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[Track]:
        if videoid:
            playlist_id = str(videoid)
        else:
            url_type, _, playlist_id = validate_youtube_url(link)
            if url_type != "playlist":
                raise ValueError("Not a valid playlist URL")
        
        url = f"{self.playlist_url}{playlist_id}"
        tracks = []
        
        try:
            playlist_info = await Playlist.get(url)
            if playlist_info:
                videos = playlist_info.get("videos", [])[:limit]
                for v in videos:
                    video_id = v.get("id") if isinstance(v, dict) else getattr(v, "id", None)
                    if video_id:
                        video_data = v if isinstance(v, dict) else v.__dict__ if hasattr(v, "__dict__") else {}
                        track = create_track_from_youtube_metadata(video_data, video_id, self.base_url)
                        if track:
                            tracks.append(track)
                if tracks:
                    return tracks
        except Exception:
            pass
        
        video_ids = await yt_dlp_get_playlist_ids(url, limit)
        for video_id in video_ids:
            metadata = await self.get_metadata("", videoid=video_id)
            if metadata:
                tracks.append(metadata)
        return tracks

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Optional[Track]:
        if videoid:
            query = f"{self.base_url}{videoid}"
        else:
            url_type, video_id, _ = validate_youtube_url(link)
            query = f"{self.base_url}{video_id}" if video_id else link
        
        results = (await VideosSearch(query, limit=10).next()).get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        
        r = results[query_type]
        return create_track_from_youtube_metadata(r, None, self.base_url)

    @capture_internal_err
    async def download(
        self,
        link: str = "",
        mystic = None,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        title: Optional[str] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        if isinstance(videoid, bool):
            videoid = None
        
        video_id = None
        if isinstance(videoid, str) and videoid.strip():
            video_id = videoid.strip()
        elif link:
            url_type, video_id, _ = validate_youtube_url(link)
        
        if not video_id:
            return (None, None)
        
        metadata = await self.get_metadata("", videoid=video_id)
        if not metadata:
            return (None, None)
        
        if isinstance(metadata, LiveTrack) and video:
            status, stream_url = await self.video("", videoid=video_id)
            return (stream_url, None) if status == 1 else (None, None)
        
        if not title:
            title = metadata.title if metadata else ""
        
        url = metadata.url
        p = await yt_dlp_download(url, type="video" if video else "audio", title=title)
        return (p, True) if p else (None, None)


YouTube = YouTubeAPI()