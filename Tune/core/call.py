# Authored By Certified Coders © 2025

import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound,
)
from pytgcalls.types import (
    AudioQuality,
    ChatUpdate,
    MediaStream,
    StreamEnded,
    Update,
    VideoQuality,
)

import config
from config import autoclean
from strings import get_string
from Tune import LOGGER, SoundCloud, YouTube, app
from Tune.misc import db, set_current_message
from Tune.platforms.Soundcloud import is_soundcloud_url
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
from Tune.utils.errors import capture_internal_err
from Tune.utils.exceptions import AssistantErr
from Tune.utils.formatters import check_duration, seconds_to_min, speed_converter
from Tune.utils.inline.play import stream_markup
from Tune.utils.stream.autoclear import auto_clean
from Tune.utils.thumbnails import get_thumb

autoend = {}
counter = {}


def dynamic_media_stream(
    path: str, video: bool = False, ffmpeg_params: str = None
) -> MediaStream:
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
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ("true", "1", "yes", "on")
    return bool(value)


async def _clear_(chat_id: int) -> None:
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
        assistants_config = [
            (config.STRING1, "TuneXAssis1"),
            (config.STRING2, "TuneXAssis2"),
            (config.STRING3, "TuneXAssis3"),
            (config.STRING4, "TuneXAssis4"),
            (config.STRING5, "TuneXAssis5"),
        ]
        assistants = []
        for string, name in assistants_config:
            userbot = (
                Client(name, config.API_ID, config.API_HASH, session_string=string)
                if string
                else None
            )
            assistant = PyTgCalls(userbot) if userbot else None
            assistants.append((userbot, assistant))
        (
            (self.userbot1, self.one),
            (self.userbot2, self.two),
            (self.userbot3, self.three),
            (self.userbot4, self.four),
            (self.userbot5, self.five),
        ) = assistants
        self.active_calls: set[int] = set()

    async def _cleanup_and_leave(self, chat_id: int, client) -> None:
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
        assistant = await group_assistant(self, chat_id)
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
        if chat_id in self.active_calls:
            try:
                await assistant.leave_call(chat_id)
            except Exception:
                pass
            finally:
                self.active_calls.discard(chat_id)
        try:
            await remove_active_video_chat(chat_id)
            await remove_active_chat(chat_id)
        except Exception:
            pass
        await _clear_(chat_id)

    @capture_internal_err
    async def skip_stream(
        self, chat_id: int, link: str, video: Union[bool, str] = None
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=_to_bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(
        self,
        chat_id: int,
        file_path: str,
        to_seek: str,
        duration: str,
        mode: str,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        stream = dynamic_media_stream(
            path=file_path, video=(mode == "video"), ffmpeg_params=ffmpeg_params
        )
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(
        self, chat_id: int, file_path: str, speed: float, playing: list
    ) -> None:
        if not isinstance(playing, list) or not playing or not isinstance(
            playing[0], dict
        ):
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
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(
            path=out,
            video=(str(playing[0].get("streamtype", "")) == "video"),
            ffmpeg_params=ffmpeg_params,
        )
        try:
            queue_check = db.get(chat_id)
            if (
                not queue_check
                or not queue_check[0]
                or queue_check[0].get("file") != file_path
            ):
                raise AssistantErr(
                    "Stream mismatch during speedup. Queue may have changed."
                )
            await assistant.play(chat_id, stream)
            old_dur = queue_check[0].get("dur")
            old_second = queue_check[0].get("seconds")
            queue_check[0].update(
                {
                    "played": con_seconds,
                    "dur": duration_min,
                    "seconds": dur,
                    "speed_path": out,
                    "speed": speed,
                    "old_dur": old_dur,
                    "old_second": old_second,
                }
            )
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
            except Exception:
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
            pass
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    def _reset_queue_progress(self, chat_id: int, current: dict) -> None:
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
            pass

    async def _send_playback_message(
        self,
        original_chat_id: int,
        img: str,
        caption: str,
        chat_id: int,
        _: dict,
        markup: str,
    ) -> None:
        button = stream_markup(_, chat_id)
        run = await app.send_photo(
            chat_id=original_chat_id,
            photo=img,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(button),
        )
        set_current_message(chat_id, run, markup)

    async def _handle_live_stream(
        self, client, chat_id: int, videoid: str, video: bool, original_chat_id: int, _: dict, current: dict
    ) -> None:
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
        title = (current["title"]).title()
        user = current["by"]
        caption = _["stream_1"].format(
            f"https://t.me/{app.username}?start=info_{videoid}",
            title[:23],
            current["dur"],
            user,
        )
        await self._send_playback_message(
            original_chat_id, img, caption, chat_id, _, "tg"
        )

    async def _handle_vid_stream(
        self, client, chat_id: int, videoid: str, video: bool, streamtype: str, title: str, original_chat_id: int, _: dict, current: dict
    ) -> None:
        mystic = await app.send_message(original_chat_id, _["call_7"])
        try:
            file_path, direct = await YouTube.download(
                videoid,
                mystic,
                videoid=True,
                video=(str(streamtype) == "video"),
                title=title,
            )
        except Exception as e:
            LOGGER(__name__).error(f"YouTube download failed in play: {e}")
            return await mystic.edit_text(_["call_6"], disable_web_page_preview=True)
        stream = dynamic_media_stream(path=file_path, video=video)
        try:
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).error(f"YouTube stream play failed: {e}")
            return await app.send_message(original_chat_id, text=_["call_6"])
        img = await get_thumb(videoid)
        user = current["by"]
        await mystic.delete()
        caption = _["stream_1"].format(
            f"https://t.me/{app.username}?start=info_{videoid}",
            title[:23],
            current["dur"],
            user,
        )
        await self._send_playback_message(
            original_chat_id, img, caption, chat_id, _, "stream"
        )

    async def _handle_soundcloud_stream(
        self, client, chat_id: int, videoid: str, queued: str, original_chat_id: int, _: dict, current: dict
    ) -> None:
        if not is_soundcloud_url(queued) and os.path.exists(str(queued)):
            file_path = queued
        else:
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
            try:
                if chat_id in db and db[chat_id] and len(db[chat_id]) > 0:
                    if queued in autoclean:
                        try:
                            autoclean.remove(queued)
                        except (ValueError, AttributeError):
                            pass
                    db[chat_id][0]["file"] = file_path
                    if file_path not in autoclean:
                        autoclean.append(file_path)
            except (IndexError, KeyError, AttributeError):
                pass
            await mystic.delete()
        stream = dynamic_media_stream(path=file_path, video=False)
        try:
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).error(f"SoundCloud play failed: {e}")
            return await app.send_message(original_chat_id, text=_["call_6"])
        img = await get_thumb(videoid)
        title = (current["title"]).title()
        user = current["by"]
        caption = _["stream_1"].format(videoid, title[:23], current["dur"], user)
        await self._send_playback_message(
            original_chat_id, img, caption, chat_id, _, "tg"
        )

    async def _handle_index_stream(
        self, client, chat_id: int, videoid: str, video: bool, original_chat_id: int, _: dict, current: dict
    ) -> None:
        if not videoid:
            return await app.send_message(original_chat_id, text=_["call_6"])
        stream = dynamic_media_stream(path=videoid, video=video)
        try:
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).error(f"Index stream play failed: {e}")
            return await app.send_message(original_chat_id, text=_["call_6"])
        user = current["by"]
        await self._send_playback_message(
            original_chat_id,
            config.STREAM_IMG_URL,
            _["stream_2"].format(user),
            chat_id,
            _,
            "tg",
        )

    async def _handle_regular_stream(
        self, client, chat_id: int, queued: str, video: bool, videoid: str, streamtype: str, original_chat_id: int, _: dict, current: dict
    ) -> None:
        if not queued:
            return await app.send_message(original_chat_id, text=_["call_6"])
        stream = dynamic_media_stream(path=queued, video=video)
        try:
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).error(f"Regular stream play failed: {e}")
            return await app.send_message(original_chat_id, text=_["call_6"])
        title = (current["title"]).title()
        user = current["by"]
        if videoid == "telegram":
            photo = (
                config.TELEGRAM_AUDIO_URL
                if str(streamtype) == "audio"
                else config.TELEGRAM_VIDEO_URL
            )
            caption = _["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], current["dur"], user
            )
            await self._send_playback_message(
                original_chat_id, photo, caption, chat_id, _, "tg"
            )
        elif videoid == "soundcloud":
            thumb_source = (
                queued
                if is_soundcloud_url(queued)
                else (videoid if is_soundcloud_url(videoid) else "soundcloud")
            )
            img = await get_thumb(thumb_source)
            caption = _["stream_1"].format(
                config.SUPPORT_CHAT, title[:23], current["dur"], user
            )
            await self._send_playback_message(
                original_chat_id, img, caption, chat_id, _, "tg"
            )
        else:
            img = await get_thumb(videoid)
            caption = _["stream_1"].format(
                f"https://t.me/{app.username}?start=info_{videoid}",
                title[:23],
                current["dur"],
                user,
            )
            try:
                await self._send_playback_message(
                    original_chat_id, img, caption, chat_id, _, "stream"
                )
            except FloodWait as e:
                LOGGER(__name__).warning(f"FloodWait: Sleeping for {e.value}")
                await asyncio.sleep(e.value)
                await self._send_playback_message(
                    original_chat_id, img, caption, chat_id, _, "stream"
                )

    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        if not check:
            return
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
        check = db.get(chat_id) or []
        if not check:
            await self._cleanup_and_leave(chat_id, client)
            return
        try:
            current = check[0]
        except (IndexError, KeyError, AttributeError):
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
        self._reset_queue_progress(chat_id, current)
        video = str(streamtype) == "video"
        if "live_" in queued:
            await self._handle_live_stream(
                client, chat_id, videoid, video, original_chat_id, _, current
            )
        elif "vid_" in queued:
            await self._handle_vid_stream(
                client, chat_id, videoid, video, streamtype, title, original_chat_id, _, current
            )
        elif videoid and is_soundcloud_url(videoid):
            await self._handle_soundcloud_stream(
                client, chat_id, videoid, queued, original_chat_id, _, current
            )
        elif "index_" in queued:
            await self._handle_index_stream(
                client, chat_id, videoid, video, original_chat_id, _, current
            )
        else:
            await self._handle_regular_stream(
                client, chat_id, queued, video, videoid, streamtype, original_chat_id, _, current
            )

    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        assistants = [self.one, self.two, self.three, self.four, self.five]
        strings = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ]
        try:
            for assistant, string in zip(assistants, strings):
                if string and assistant:
                    await assistant.start()
        except Exception as e:
            LOGGER(__name__).error(f"Error starting PyTgCalls clients: {e}")

    @capture_internal_err
    async def ping(self) -> str:
        assistants = [self.one, self.two, self.three, self.four, self.five]
        strings = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ]
        pings = []
        try:
            for assistant, string in zip(assistants, strings):
                if string and assistant:
                    pings.append(assistant.ping)
        except Exception:
            pass
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(
            filter(None, [self.one, self.two, self.three, self.four, self.five])
        )
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
                            LOGGER(__name__).error(
                                f"Error in StreamEnded handler: {e}"
                            )
                elif isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        try:
                            await self.stop_stream(update.chat_id)
                        except Exception as e:
                            LOGGER(__name__).error(
                                f"Error in ChatUpdate handler: {e}"
                            )
                        return
            except Exception as e:
                LOGGER(__name__).error(f"Error in unified_update_handler: {e}")

        for assistant in assistants:
            if assistant:
                try:
                    assistant.on_update()(unified_update_handler)
                except Exception as e:
                    LOGGER(__name__).error(
                        f"Error registering update handler: {e}"
                    )


StreamController = Call()
