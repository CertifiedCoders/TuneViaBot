# Authored By Certified Coders © 2025

import asyncio
import os
from dataclasses import dataclass
from typing import Dict, Optional

CPU = os.cpu_count() or 4
MAX_CONCURRENT = min(128, CPU * 16)
CHUNK_SIZE = 256 * 1024
YTDLP_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 300
JOIN_CALL_TIMEOUT = 30
SEM = asyncio.Semaphore(MAX_CONCURRENT)
CHAT_SEMAPHORES = {}
CHAT_SEMAPHORE_LOCK = asyncio.Lock()

async def get_chat_semaphore(chat_id: int):
    async with CHAT_SEMAPHORE_LOCK:
        return CHAT_SEMAPHORES.setdefault(chat_id, asyncio.Semaphore(3))


@dataclass
class Track:
    id: str
    title: str
    url: str
    duration_min: Optional[str] = None
    duration_sec: int = 0
    thumbnail: str = None
    file_path: str = None
    message_id: int = 0
    time: int = 0
    user: str = None
    video: bool = False
    channel_name: str = None
    view_count: str = None
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "link": self.url,
            "vidid": self.id,
            "duration_min": self.duration_min,
            "thumb": self.thumbnail or "",
            "view_count": self.view_count,
        }


@dataclass
class LiveTrack:
    id: str
    title: str
    url: str
    thumbnail: str = None
    file_path: str = None
    message_id: int = 0
    time: int = 0
    user: str = None
    video: bool = False
    channel_name: str = None
    view_count: str = None
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "link": self.url,
            "vidid": self.id,
            "duration_min": None,
            "thumb": self.thumbnail or "",
            "view_count": self.view_count,
        }
