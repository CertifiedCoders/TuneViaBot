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
from Tune.utils.decorators.language import language_no_delete
from Tune.utils.pastebin import TuneBin
from strings import get_string

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def cleanup_storage():
    always_clean = ["raw_files", "logs"]
    
    if config.CLEANUP_MEDIA_ON_RESTART:
        folders_to_clean = ["downloads", "cache"] + always_clean
    else:
        folders_to_clean = always_clean
        LOGGER(__name__).info("Media cleanup disabled: preserving downloads and cache folders")
    
    for folder in folders_to_clean:
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
        except (OSError, PermissionError, shutil.Error) as e:
            LOGGER(__name__).warning(f"Failed to delete {folder}: {e}")

    for root, dirs, _ in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                try:
                    shutil.rmtree(os.path.join(root, d))
                except (OSError, PermissionError, shutil.Error):
                    pass


def _ordinal(n: int) -> str:
    suffix = "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4]
    return f"{n}{suffix}"


async def notify_active_chats(_):
    try:
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                await app.send_message(
                    chat_id=int(chat_id),
                    text=_["server_8"].format(app.mention),
                )
                await remove_active_chat(chat_id)
                await remove_active_video_chat(chat_id)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to notify chat {chat_id}: {e}")
    except Exception as e:
        LOGGER(__name__).error(f"Failed to get active chats: {e}")


@app.on_message(filters.command(["getlog", "logs", "getlogs"]) & SUDOERS)
@language_no_delete
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
@language_no_delete
async def update_(client, message, _):
    if is_heroku() and HAPP is None:
        return await message.reply_text(_["server_2"])

    response = await message.reply_text(_["server_3"])

    try:
        repo = Repo()
    except (GitCommandError, InvalidGitRepositoryError):
        return await response.edit(_["server_4"])
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

    try:
        repo_url = repo.remotes.origin.url.split(".git")[0]
        commits = list(repo.iter_commits(f"HEAD..origin/{config.UPSTREAM_BRANCH}"))
        if not commits:
            return await response.edit(_["server_6"])
    except Exception as e:
        LOGGER(__name__).error(f"Failed to check for updates: {e}")
        return await response.edit(_["server_4"])

    updates = ""
    try:
        for commit in commits:
            commit_date = datetime.fromtimestamp(commit.committed_date)
            day_ordinal = _ordinal(int(commit_date.strftime("%d")))
            updates += (
                f"<b>\u2793 #{commit.count()}: <a href={repo_url}/commit/{commit}>{commit.summary}</a> {_['server_22']} {commit.author}</b>\n"
                f"\t\t\t\t<b>\u279e {_['server_23']}</b> {day_ordinal} "
                f"{commit_date.strftime('%b')}, {commit_date.strftime('%Y')}\n\n"
            )
    except Exception as e:
        LOGGER(__name__).error(f"Failed to parse commit information: {e}")
        return await response.edit(_["server_4"])

    update_header = (
        f"<b>{_['server_18']}</b>\n\n"
        f"\u2793 {_['server_19']}\n\n"
        f"<b><u>{_['server_20']}</u></b>\n\n"
    )
    final_message = update_header + updates

    try:
        if len(final_message) > 4096:
            url = await TuneBin(updates)
            nrs = await response.edit(
                f"<b>{_['server_18']}</b>\n\n"
                f"\u2793 {_['server_19']}\n\n"
                f"<u><b>{_['server_20']}</b></u>\n\n"
                f"<a href={url}>{_['server_21']}</a>"
            )
        else:
            nrs = await response.edit(final_message, disable_web_page_preview=True)
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

    await notify_active_chats(_)

    try:
        await response.edit(f"{nrs.text}\n\n{_['server_7']}")
    except Exception:
        pass

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

    os.execv(sys.executable, [sys.executable, "-m", "Tune"])


@app.on_message(filters.command(["restart"]) & SUDOERS)
async def restart_(_, message):
    try:
        from Tune.utils.database import get_lang
        language = await get_lang(message.chat.id)
        _ = get_string(language)
    except Exception:
        _ = get_string("en")

    response = await message.reply_text(_["server_16"])
    await notify_active_chats(_)
    cleanup_storage()

    try:
        await response.edit_text(_["server_17"])
    except Exception:
        pass

    os.execv(sys.executable, [sys.executable, "-m", "Tune"])
