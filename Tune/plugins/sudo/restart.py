# Authored By Certified Coders © 2025
import asyncio
import os
import shutil
import sys
from datetime import datetime

import urllib3
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from pyrogram import filters

import config
from Tune import app
from Tune.logging import LOGGER
from Tune.misc import HAPP, SUDOERS, XCB, is_heroku
from Tune.utils.database import (
    get_active_chats,
    remove_active_chat,
    remove_active_video_chat,
)
from Tune.utils.decorators.language import language
from Tune.utils.pastebin import TuneBin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def cleanup_storage():
    folders_to_remove = ["downloads", "raw_files", "cache"]
    for folder in folders_to_remove:
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except (OSError, PermissionError, shutil.Error) as e:
            LOGGER(__name__).warning(f"Failed to delete {folder}: {e}")

    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d))
                except (OSError, PermissionError, shutil.Error):
                    pass


def _ordinal(n: int) -> str:
    suffix = "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4]
    return f"{n}{suffix}"


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & SUDOERS)
@language
async def log_(client, message, _):
    try:
        if os.path.exists("log.txt"):
            await message.reply_document(document="log.txt")
        else:
            await message.reply_text(_["server_1"])
    except Exception as e:
        LOGGER(__name__).error(f"Failed to send log file: {e}")
        await message.reply_text(_["server_1"])


@app.on_message(filters.command(["update", "gitpull"]) & SUDOERS)
@language
async def update_(client, message, _):
    if is_heroku():
        if HAPP is None:
            return await message.reply_text(_["server_2"])

    response = await message.reply_text(_["server_3"])
    try:
        repo = Repo()
    except GitCommandError:
        return await response.edit(_["server_4"])
    except InvalidGitRepositoryError:
        return await response.edit(_["server_5"])
    except Exception as e:
        LOGGER(__name__).error(f"Unexpected error accessing repository: {e}")
        return await response.edit(_["server_4"])

    try:
        process = await asyncio.create_subprocess_shell(
            f"git fetch origin {config.UPSTREAM_BRANCH}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        LOGGER(__name__).warning("Git fetch timed out")
    except Exception as e:
        LOGGER(__name__).error(f"Git fetch failed: {e}")

    await asyncio.sleep(2)

    verification = ""
    try:
        REPO_ = repo.remotes.origin.url.split(".git")[0]
        for checks in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
            verification = str(checks.count())
            break
    except Exception as e:
        LOGGER(__name__).error(f"Failed to check for updates: {e}")
        return await response.edit(_["server_4"])

    if not verification:
        return await response.edit(_["server_6"])

    updates = ""
    try:
        for info in repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"):
            commit_date = datetime.fromtimestamp(info.committed_date)
            day_ordinal = _ordinal(int(commit_date.strftime("%d")))
            updates += (
                f"<b>\u2793 #{info.count()}: <a href={REPO_}/commit/{info}>{info.summary}</a> ʙʏ -> {info.author}</b>\n"
                f"\t\t\t\t<b>\u279e ᴄᴏᴍᴍɪᴛᴇᴅ ᴏɴ :</b> {day_ordinal} "
                f"{commit_date.strftime('%b')}, {commit_date.strftime('%Y')}\n\n"
            )
    except Exception as e:
        LOGGER(__name__).error(f"Failed to parse commit information: {e}")
        return await response.edit(_["server_4"])

    _update_response_ = (
        "<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n"
        "\u2793 ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n"
        "<b><u>ᴜᴩᴅᴀᴛᴇs:</u></b>\n\n"
    )
    _final_updates_ = _update_response_ + updates

    try:
        if len(_final_updates_) > 4096:
            url = await TuneBin(updates)
            nrs = await response.edit(
                f"<b>ᴀ ɴᴇᴡ ᴜᴩᴅᴀᴛᴇ ɪs ᴀᴠᴀɪʟᴀʙʟᴇ ғᴏʀ ᴛʜᴇ ʙᴏᴛ !</b>\n\n"
                f"\u2793 ᴩᴜsʜɪɴɢ ᴜᴩᴅᴀᴛᴇs ɴᴏᴡ\n\n"
                f"<u><b>ᴜᴩᴅᴀᴛᴇs :</b></u>\n\n<a href={url}>ᴄʜᴇᴄᴋ ᴜᴩᴅᴀᴛᴇs</a>"
            )
        else:
            nrs = await response.edit(_final_updates_, disable_web_page_preview=True)
    except Exception as e:
        LOGGER(__name__).error(f"Failed to send update message: {e}")
        nrs = response

    try:
        process = await asyncio.create_subprocess_shell(
            "git stash && git pull",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        LOGGER(__name__).warning("Git pull timed out")
    except Exception as e:
        LOGGER(__name__).error(f"Git pull failed: {e}")

    try:
        served_chats = await get_active_chats()
        for x in served_chats:
            try:
                await app.send_message(
                    chat_id=int(x), text=_["server_8"].format(app.mention)
                )
                await remove_active_chat(x)
                await remove_active_video_chat(x)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to notify chat {x}: {e}")
        await response.edit(f"{nrs.text}\n\n{_['server_7']}")
    except Exception as e:
        LOGGER(__name__).error(f"Failed to notify active chats: {e}")

    cleanup_storage()

    if is_heroku():
        try:
            heroku_command = f"{XCB[5]} {XCB[7]} {XCB[9]}{XCB[4]}{XCB[0]*2}{XCB[6]}{XCB[4]}{XCB[8]}{XCB[1]}{XCB[5]}{XCB[2]}{XCB[6]}{XCB[2]}{XCB[3]}{XCB[0]}{XCB[10]}{XCB[2]}{XCB[5]} {XCB[11]}{XCB[4]}{XCB[12]}"
            process = await asyncio.create_subprocess_shell(
                heroku_command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()
            return
        except Exception as err:
            LOGGER(__name__).error(f"Heroku deployment failed: {err}")
            await response.edit(f"{nrs.text}\n\n{_['server_9']}")
            try:
                await app.send_message(
                    chat_id=config.LOGGER_ID,
                    text=_["server_10"].format(err),
                )
            except Exception:
                pass
            return
    else:
        os.execv(sys.executable, [sys.executable, "-m", "Tune"])


@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    response = await message.reply_text("ʀᴇsᴛᴀʀᴛɪɴɢ...")
    try:
        ac_chats = await get_active_chats()
        for x in ac_chats:
            try:
                await app.send_message(
                    chat_id=int(x),
                    text=f"{app.mention} ɪs ʀᴇsᴛᴀʀᴛɪɴɢ...\n\nʏᴏᴜ ᴄᴀɴ sᴛᴀʀᴛ ᴩʟᴀʏɪɴɢ ᴀɢᴀɪɴ ᴀғᴛᴇʀ 15-20 sᴇᴄᴏɴᴅs.",
                )
                await remove_active_chat(x)
                await remove_active_video_chat(x)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to notify chat {x} during restart: {e}")
    except Exception as e:
        LOGGER(__name__).error(f"Failed to get active chats during restart: {e}")

    cleanup_storage()

    try:
        await response.edit_text(
            "» ʀᴇsᴛᴀʀᴛ ᴘʀᴏᴄᴇss sᴛᴀʀᴛᴇᴅ, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴜɴᴛɪʟ ᴛʜᴇ ʙᴏᴛ sᴛᴀʀᴛs..."
        )
    except Exception:
        pass

    os.execv(sys.executable, [sys.executable, "-m", "Tune"])
