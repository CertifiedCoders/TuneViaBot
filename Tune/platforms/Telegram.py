# Authored By Certified Coders © 2025
import asyncio
import os
import time
from typing import Optional, Union

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Voice

import config
from Tune import app
from Tune.utils.formatters import (
    check_duration,
    convert_bytes,
    get_readable_time,
    seconds_to_min,
)


class TeleAPI:
    async def get_link(self, message):
        return message.link

    async def get_filename(self, file, audio: Union[bool, str] = None) -> str:
        file_name = getattr(file, "file_name", None)
        return file_name or ("ᴛᴇʟᴇɢʀᴀᴍ ᴀᴜᴅɪᴏ" if audio else "ᴛᴇʟᴇɢʀᴀᴍ ᴠɪᴅᴇᴏ")

    async def get_duration(self, file_obj, file_path: Optional[str] = None) -> str:
        if hasattr(file_obj, "duration") and file_obj.duration:
            return seconds_to_min(file_obj.duration)
        
        if file_path:
            try:
                dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, file_path)
                return seconds_to_min(dur)
            except Exception:
                pass
        
        return "Unknown"

    async def get_filepath(
        self,
        audio: Union[bool, str] = None,
        video: Union[bool, str] = None,
    ) -> str:
        base = os.path.realpath("downloads")
        
        if audio:
            if isinstance(audio, Voice):
                ext = "ogg"
            else:
                try:
                    ext = audio.file_name.split(".")[-1]
                except Exception:
                    ext = "ogg"
            return os.path.join(base, f"{audio.file_unique_id}.{ext}")
        
        if video:
            try:
                ext = video.file_name.split(".")[-1]
            except Exception:
                ext = "mp4"
            return os.path.join(base, f"{video.file_unique_id}.{ext}")
        
        return os.path.join(base, f"{int(time.time())}.dat")

    async def download(self, _, message, mystic, fname: str) -> bool:
        if os.path.exists(fname):
            return True

        speed_counter = {message.id: time.time()}

        async def download_task():
            updated_thresholds = set()
            
            async def progress(current, total):
                if current == total or total == 0:
                    return
                
                elapsed = max(time.time() - speed_counter[message.id], 1e-3)
                percentage = int(current * 100 / total)
                
                progress_ranges = [(0, 5), (8, 10), (17, 20), (38, 40), (64, 66), (77, 80), (96, 99)]
                
                for low, high in progress_ranges:
                    if low < percentage <= high:
                        if high in updated_thresholds:
                            return
                        updated_thresholds.add(high)
                        break
                else:
                    return
                
                try:
                    speed = current / elapsed
                    eta_s = int((total - current) / max(speed, 1e-6))
                except Exception:
                    speed, eta_s = 0, 0

                upl = InlineKeyboardMarkup(
                    [[InlineKeyboardButton(text="ᴄᴀɴᴄᴇʟ", callback_data="stop_downloading")]]
                )
                
                await mystic.edit_text(
                    text=_["tg_1"].format(
                        app.mention,
                        convert_bytes(total),
                        convert_bytes(current),
                        str(percentage)[:5],
                        convert_bytes(speed),
                        get_readable_time(eta_s) or "0 sᴇᴄᴏɴᴅs"
                    ),
                    reply_markup=upl,
                )

            try:
                await app.download_media(message.reply_to_message, file_name=fname, progress=progress)
                elapsed = get_readable_time(int(time.time() - speed_counter[message.id]))
                await mystic.edit_text(_["tg_2"].format(elapsed))
            except Exception:
                await mystic.edit_text(_["tg_3"])

        task = asyncio.create_task(download_task())
        config.lyrical[mystic.id] = task
        await task
        
        if mystic.id not in config.lyrical:
            return False
        config.lyrical.pop(mystic.id, None)
        return True
