# Authored By Certified Coders © 2025

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError, ConnectionNotFound
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall, NoAudioSourceFound, NoVideoSourceFound
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from config import autoclean
from strings import get_string
from Tune import LOGGER, SoundCloud, YouTube, app
from Tune.misc import db, set_current_message
from Tune.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from Tune.utils.exceptions import AssistantErr
from Tune.utils.formatters import check_duration, seconds_to_min, speed_converter
from Tune.utils.inline.play import stream_markup
from Tune.utils.stream.autoclear import auto_clean
from Tune.utils.thumbnails import get_thumb
from Tune.utils.errors import capture_internal_err

autoend = {}
counter = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    """Create a MediaStream object optimized for audio or video playback."""
    if video:
        return MediaStream(
            media_path=path,
            audio_parameters=AudioQuality.HIGH,
            video_parameters=VideoQuality.HD_720p,
            audio_flags=MediaStream.Flags.REQUIRED,
            video_flags=MediaStream.Flags.REQUIRED,
            ffmpeg_parameters=ffmpeg_params,
        )
    return MediaStream(
        media_path=path,
        audio_parameters=AudioQuality.HIGH,
        audio_flags=MediaStream.Flags.REQUIRED,
        video_flags=MediaStream.Flags.IGNORE,
        ffmpeg_parameters=ffmpeg_params,
    )

def _to_bool(value: Union[bool, str, None]) -> bool:
    """
    Safely convert a value to boolean, handling both bool and string types.
    String values like "false", "0", "no" are treated as False,
    while "true", "1", "yes" (case-insensitive) are treated as True.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ("true", "1", "yes", "on")
    return bool(value)


async def _clear_(chat_id: int) -> None:
    """Clear queue state and clean up downloaded files for a chat."""
    popped = db.pop(chat_id, None)
    if popped:
        for item in popped:
            try:
                await auto_clean(item)
            except Exception:
                pass
    db[chat_id] = []
    try:
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception:
        pass

class Call:
    def __init__(self):
        self.userbot1 = Client(
            "TuneXAssis1", config.API_ID, config.API_HASH, session_string=config.STRING1
        ) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "TuneXAssis2", config.API_ID, config.API_HASH, session_string=config.STRING2
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "TuneXAssis3", config.API_ID, config.API_HASH, session_string=config.STRING3
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "TuneXAssis4", config.API_ID, config.API_HASH, session_string=config.STRING4
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "TuneXAssis5", config.API_ID, config.API_HASH, session_string=config.STRING5
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()

    async def _cleanup_and_leave(self, chat_id: int, client) -> None:
        """Helper to cleanup queue state and leave voice call."""
        try:
            await _clear_(chat_id)
        except Exception:
            pass
        if chat_id in self.active_calls:
            try:
                await client.leave_call(chat_id)
            except (NoActiveGroupCall, Exception):
                pass
            finally:
                self.active_calls.discard(chat_id)


    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)


    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        """Force stop playback, cleanup current track, and leave call immediately."""
        assistant = await group_assistant(self, chat_id)
        
        # Cleanup current track if exists
        try:
            check = db.get(chat_id)
            if check:
                popped_item = check.pop(0)
                if popped_item:
                    try:
                        await auto_clean(popped_item)
                    except Exception:
                        pass
        except (IndexError, KeyError, AttributeError):
            pass
        
        # Leave call first to stop playback immediately
        if chat_id in self.active_calls:
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)
        
        # Cleanup remaining state
        try:
            await remove_active_video_chat(chat_id)
            await remove_active_chat(chat_id)
        except Exception:
            pass
        await _clear_(chat_id)


    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None) -> None:
        """Skip to a new stream URL immediately."""
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=_to_bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Invalid stream info for speedup.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f'ffmpeg -i "{file_path}" -filter:v "setpts={vs}*PTS" -filter:a atempo={speed} -y "{out}"'
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise AssistantErr("Failed to process speed change with ffmpeg.")

        loop = asyncio.get_running_loop()
        dur = int(await loop.run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = str(playing[0].get("streamtype", "")) == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        try:
            queue_check = db.get(chat_id)
            if not queue_check or not queue_check[0] or queue_check[0].get("file") != file_path:
                raise AssistantErr("Stream mismatch during speedup. Queue may have changed.")
            
            await assistant.play(chat_id, stream)
            old_dur = queue_check[0].get("dur")
            old_second = queue_check[0].get("seconds")
            queue_check[0].update({
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": speed,
                "old_dur": old_dur,
                "old_second": old_second,
            })
        except (IndexError, KeyError, AttributeError) as e:
            raise AssistantErr(f"Stream mismatch during speedup: {str(e)}")


    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await assistant.play(config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        is_video = _to_bool(video)
        stream = dynamic_media_stream(path=link, video=is_video)

        try:
            await assistant.play(chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except NoAudioSourceFound:
            raise AssistantErr(_["call_11"])
        except NoVideoSourceFound:
            raise AssistantErr(_["call_12"])
        except Exception as e:
            raise AssistantErr(
                f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {e}"
            )
        self.active_calls.add(chat_id)
        try:
            await add_active_chat(chat_id)
            await music_on(chat_id)
            if is_video:
                await add_active_video_chat(chat_id)
        except Exception:
            # If database operations fail, we still have the call active
            pass

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)


    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        if not check:
            return
        
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
                if popped:
                    try:
                        await auto_clean(popped)
                    except Exception:
                        pass
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            
            if not check:
                await self._cleanup_and_leave(chat_id, client)
                return
        except (IndexError, KeyError, AttributeError):
            await self._cleanup_and_leave(chat_id, client)
            return
        except Exception as e:
            LOGGER(__name__).error(f"Error in play method: {e}")
            await self._cleanup_and_leave(chat_id, client)
            return
        else:
            # Re-read queue to handle possible concurrent modifications
            check = db.get(chat_id) or []
            if not check:
                # Queue became empty after popping/cleaning; nothing to play
                await self._cleanup_and_leave(chat_id, client)
                return

            # Wrap queue access in exception handling to catch concurrent modifications
            try:
                current = check[0]
            except (IndexError, KeyError, AttributeError):
                # Queue was emptied/modified between check and access
                await self._cleanup_and_leave(chat_id, client)
                return

            queued = current["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (current["title"]).title()
            user = current["by"]
            original_chat_id = current["chat_id"]
            streamtype = current["streamtype"]
            videoid = current["vidid"]

            # Reset playback progress for the new current track, if the queue still exists.
            # Wrapped in a narrow try/except so concurrent queue clears can't raise IndexError/KeyError.
            try:
                if chat_id in db and db[chat_id]:
                    db[chat_id][0]["played"] = 0
                    exis = current.get("old_dur")
                    if exis:
                        db[chat_id][0]["dur"] = exis
                        db[chat_id][0]["seconds"] = current["old_second"]
                        db[chat_id][0]["speed_path"] = None
                        db[chat_id][0]["speed"] = 1.0
            except (IndexError, KeyError):
                # Queue was modified or cleared concurrently; nothing left to reset.
                pass

            video = str(streamtype) == "video"

            if "live_" in queued:
                try:
                    n, link = await YouTube.video(videoid, True)
                    if n == 0 or not link:
                        return await app.send_message(original_chat_id, text=_["call_6"])

                    stream = dynamic_media_stream(path=link, video=video)
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"Live stream play failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        current["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                set_current_message(chat_id, run, "tg")

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=str(streamtype) == "video",
                        title=title,
                    )
                except Exception as e:
                    LOGGER(__name__).error(f"YouTube download failed in play: {e}")
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )

                stream = dynamic_media_stream(path=file_path, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"YouTube stream play failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        current["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                set_current_message(chat_id, run, "stream")

            elif videoid and ("soundcloud.com" in str(videoid) or "on.soundcloud.com" in str(videoid)):
                # Handle SoundCloud tracks (check videoid since it always contains the URL)
                # queued may be either a URL (from playlist queuing) or a file path (already downloaded)
                
                # Check if queued is already a downloaded file path (not a URL)
                if "soundcloud.com" not in str(queued) and "on.soundcloud.com" not in str(queued) and os.path.exists(str(queued)):
                    # File is already downloaded, use it directly
                    file_path = queued
                else:
                    # Need to download from the URL in videoid
                    mystic = await app.send_message(original_chat_id, _["call_7"])
                    try:
                        result = await SoundCloud.download(videoid)
                        if result is False or not isinstance(result, tuple):
                            return await mystic.edit_text(
                                _["call_6"], disable_web_page_preview=True
                            )
                        details_dict, file_path = result
                    except Exception as e:
                        LOGGER(__name__).error(f"SoundCloud download failed in play: {e}")
                        return await mystic.edit_text(
                            _["call_6"], disable_web_page_preview=True
                        )

                    # Update the queue entry to store the actual file path instead of URL
                    # This ensures auto_clean can properly delete the file later
                    try:
                        if chat_id in db and db[chat_id] and len(db[chat_id]) > 0:
                            # Remove the URL from autoclean if it was added
                            if queued in autoclean:
                                try:
                                    autoclean.remove(queued)
                                except (ValueError, AttributeError):
                                    pass
                            # Update the queue entry with the actual file path
                            db[chat_id][0]["file"] = file_path
                            # Add the file path to autoclean for cleanup later
                            if file_path not in autoclean:
                                autoclean.append(file_path)
                    except (IndexError, KeyError, AttributeError):
                        # Queue was modified concurrently; continue anyway
                        pass
                    await mystic.delete()

                stream = dynamic_media_stream(path=file_path, video=False)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"SoundCloud play failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                # Use videoid (URL) for thumbnail since it always contains the SoundCloud URL
                img = await get_thumb(videoid)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        videoid,
                        title[:23],
                        current["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                set_current_message(chat_id, run, "tg")

            elif "index_" in queued:
                if not videoid:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                stream = dynamic_media_stream(path=videoid, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"Index stream play failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                set_current_message(chat_id, run, "tg")

            else:
                if not queued:
                    return await app.send_message(original_chat_id, text=_["call_6"])
                stream = dynamic_media_stream(path=queued, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"Regular stream play failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], current["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    set_current_message(chat_id, run, "tg")

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    # Try to get thumbnail from queued URL if it's a SoundCloud URL, otherwise use videoid or fallback
                    thumb_source = queued if ("soundcloud.com" in str(queued) or "on.soundcloud.com" in str(queued)) else (videoid if ("soundcloud.com" in str(videoid) or "on.soundcloud.com" in str(videoid)) else "soundcloud")
                    img = await get_thumb(thumb_source)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=img,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], current["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    set_current_message(chat_id, run, "tg")

                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                current["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except FloodWait as e:
                        LOGGER(__name__).warning(f"FloodWait: Sleeping for {e.value}")
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                current["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    set_current_message(chat_id, run, "stream")


    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        try:
            if config.STRING1 and self.one:
                await self.one.start()
            if config.STRING2 and self.two:
                await self.two.start()
            if config.STRING3 and self.three:
                await self.three.start()
            if config.STRING4 and self.four:
                await self.four.start()
            if config.STRING5 and self.five:
                await self.five.start()
        except Exception as e:
            LOGGER(__name__).error(f"Error starting PyTgCalls clients: {e}")

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        try:
            if config.STRING1 and self.one:
                pings.append(self.one.ping)
            if config.STRING2 and self.two:
                pings.append(self.two.ping)
            if config.STRING3 and self.three:
                pings.append(self.three.ping)
            if config.STRING4 and self.four:
                pings.append(self.four.ping)
            if config.STRING5 and self.five:
                pings.append(self.five.ping)
        except Exception:
            pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, StreamEnded):
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        try:
                            assistant = await group_assistant(self, update.chat_id)
                            if assistant:
                                await self.play(assistant, update.chat_id)
                        except Exception as e:
                            LOGGER(__name__).error(f"Error in StreamEnded handler: {e}")
                
                elif isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        try:
                            await self.stop_stream(update.chat_id)
                        except Exception as e:
                            LOGGER(__name__).error(f"Error in ChatUpdate handler: {e}")
                        return
            except Exception as e:
                LOGGER(__name__).error(f"Error in unified_update_handler: {e}")

        for assistant in assistants:
            if assistant:
                try:
                    assistant.on_update()(unified_update_handler)
                except Exception as e:
                    LOGGER(__name__).error(f"Error registering update handler: {e}")


StreamController = Call()
