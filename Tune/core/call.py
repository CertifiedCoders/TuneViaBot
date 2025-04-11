import asyncio
import os
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import (
    AudioQuality,
    ChatUpdate,
    MediaStream,
    StreamEnded,
    Update,
    UpdatedGroupCallParticipant,
    VideoQuality,
)

import config
from strings import get_string
from Tune import LOGGER, YouTube, app
from Tune.misc import db
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

autoend = {}
counter = {}


async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)


def dynamic_media_stream(
    path: str, video: bool = False, ffmpeg_params: str = None
) -> MediaStream:
    return MediaStream(
        audio_path=path,
        media_path=path,
        audio_parameters=AudioQuality.MEDIUM if video else AudioQuality.STUDIO,
        video_parameters=VideoQuality.HD_720p if video else VideoQuality.SD_360p,
        video_flags=(
            MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE
        ),
        ffmpeg_parameters=ffmpeg_params,
    )


class Call:
    def __init__(self):
        self.userbot1 = Client(
            "TuneViaAssis1",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1)

        self.userbot2 = Client(
            "TuneViaAssis2",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2)

        self.userbot3 = Client(
            "TuneViaAssis3",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3)

        self.userbot4 = Client(
            "TuneViaAssis4",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4)

        self.userbot5 = Client(
            "TuneViaAssis5",
            config.API_ID,
            config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5)

    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await _clear_(chat_id)
        await assistant.leave_call(chat_id)

    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass

        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)

        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await assistant.play(chat_id, stream)

    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    async def change_volume(self, chat_id: int, volume: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.change_volume_call(chat_id, volume)

    async def seek_stream(
        self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(
            path=file_path, video=is_video, ffmpeg_params=ffmpeg_params
        )
        await assistant.play(chat_id, stream)

    async def speedup_stream(
        self, chat_id: int, file_path: str, speed: float, playing: list
    ) -> None:
        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            cmd = f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}"
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        dur = int(
            await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        )
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"

        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(
            path=out, video=is_video, ffmpeg_params=ffmpeg_params
        )

        if db[chat_id][0]["file"] == file_path:
            await assistant.play(chat_id, stream)
        else:
            raise AssistantErr("Stream mismatch during speedup.")

        db[chat_id][0].update(
            {
                "played": con_seconds,
                "dur": duration_min,
                "seconds": dur,
                "speed_path": out,
                "speed": speed,
                "old_dur": db[chat_id][0].get("dur"),
                "old_second": db[chat_id][0].get("seconds"),
            }
        )

    async def stream_call(self, link: str) -> None:
        assistant = await group_assistant(self, config.LOGGER_ID)
        await assistant.play(config.LOGGER_ID, MediaStream(link))
        await asyncio.sleep(4)
        await assistant.leave_call(config.LOGGER_ID)

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

        stream = dynamic_media_stream(path=link, video=bool(video))

        try:
            await assistant.play(chat_id, stream)
        except NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(f"Unable to join the group call. Reason: {str(e)}")

        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except:
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )

                stream = dynamic_media_stream(path=file_path, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
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
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                stream = dynamic_media_stream(path=videoid, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = dynamic_media_stream(path=queued, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
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
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

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
                                check[0]["dur"],
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
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def decorators(self) -> None:
        assistants = [self.one, self.two, self.three, self.four, self.five]

        for assistant in assistants:

            @assistant.on_update()
            async def unified_update_handler(client, update: Update) -> None:
                try:
                    if isinstance(update, ChatUpdate):
                        if ChatUpdate.Status.LEFT_CALL in update.status:
                            LOGGER(__name__).warning(
                                f"[ChatUpdate] Bot left or was removed from call: Chat {update.chat_id} | Status: {update.status}"
                            )
                            await self.stop_stream(update.chat_id)
                            return

                        critical_flags = (
                            update.status & ChatUpdate.Status.KICKED
                            or update.status & ChatUpdate.Status.LEFT_GROUP
                            or update.status & ChatUpdate.Status.CLOSED_VOICE_CHAT
                            or update.status & ChatUpdate.Status.DISCARDED_CALL
                            or update.status & ChatUpdate.Status.BUSY_CALL
                        )
                        if critical_flags:
                            LOGGER(__name__).warning(
                                f"[ChatUpdate] Critical event in Chat {update.chat_id}: {update.status}. Stopping stream."
                            )
                            await self.stop_stream(update.chat_id)
                            return

                    elif isinstance(update, StreamEnded):
                        if update.stream_type != StreamEnded.Type.AUDIO:
                            return
                        LOGGER(__name__).info(
                            f"[StreamEnded] Audio stream ended in Chat: {update.chat_id}"
                        )
                        await self.play(client, update.chat_id)

                    elif isinstance(update, UpdatedGroupCallParticipant):
                        p = update.participant
                        flags = []
                        if p.action.name == "JOINED":
                            flags.append("🟢 Joined")
                        elif p.action.name == "LEFT":
                            flags.append("🔴 Left")
                        else:
                            flags.append("🔄 Updated")
                        if p.muted:
                            flags.append("Muted")
                        if p.muted_by_admin:
                            flags.append("Muted by Admin")
                        if p.video:
                            flags.append("Video On")
                        if p.screen_sharing:
                            flags.append("Screen Sharing")
                        if p.raised_hand:
                            flags.append("✋ Raised Hand")
                        LOGGER(__name__).info(
                            f"[ParticipantUpdate] Chat: {update.chat_id} | User: {p.user_id} | "
                            f"{', '.join(flags)} | Volume: {p.volume}"
                        )
                except Exception as e:
                    LOGGER(__name__).error(
                        f"[UnifiedUpdateHandler Error] {type(update).__name__} | {e}"
                    )


Jarvis = Call()
