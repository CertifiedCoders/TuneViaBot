# Authored By Certified Coders © 2025
import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import BANNED_USERS
from Tune import LOGGER, app, userbot
from Tune.core.call import StreamController
from Tune.core.userbot import get_session_count
from Tune.misc import sudo
from Tune.plugins import ALL_MODULES
from Tune.plugins.security.antispam_handler import get_spam_blocked_cache, log_antispam_status
from Tune.utils.cookie_handler import fetch_and_store_cookies
from Tune.utils.database import get_banned_users, get_gbanned, get_spam_blocked_users


async def init():
    session_count = get_session_count()
    if session_count == 0:
        LOGGER(__name__).error("ᴀssɪsᴛᴀɴᴛ sᴇssɪᴏɴ ɴᴏᴛ ғɪʟʟᴇᴅ, ᴘʟᴇᴀsᴇ ғɪʟʟ ᴀ ᴘʏʀᴏɢʀᴀᴍ sᴇssɪᴏɴ...")
        exit()

    try:
        await fetch_and_store_cookies()
        LOGGER("Tune").info("ʏᴏᴜᴛᴜʙᴇ ᴄᴏᴏᴋɪᴇs ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ✅")
    except Exception as e:
        LOGGER("Tune").warning(f"⚠️ᴄᴏᴏᴋɪᴇ ᴇʀʀᴏʀ: {e}")

    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
        spam_users = await get_spam_blocked_users()
        cache = get_spam_blocked_cache()
        for user_id in spam_users:
            cache.add(user_id)
    except Exception as e:
        LOGGER("Tune").warning(f"ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ ʙᴀɴɴᴇᴅ ᴜsᴇʀs: {e}")

    await app.start()

    for all_module in ALL_MODULES:
        importlib.import_module("Tune.plugins" + all_module)

    LOGGER("Tune.plugins").info("ᴛᴜɴᴇ's ᴍᴏᴅᴜʟᴇs ʟᴏᴀᴅᴇᴅ...")
    enabled, cmd_count = await log_antispam_status()
    if enabled:
        LOGGER("Tune").info(f"Aɴᴛɪsᴘᴀᴍ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ᴇɴᴀʙʟᴇᴅ ɪɴsɪᴅᴇ {cmd_count} ᴄᴏᴍᴍᴀɴᴅs ✅")
    await userbot.start()
    await StreamController.start()

    try:
        await StreamController.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("Tune").error(
            "ᴘʟᴇᴀsᴇ ᴛᴜʀɴ ᴏɴ ᴛʜᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴏғ ʏᴏᴜʀ ʟᴏɢ ɢʀᴏᴜᴘ/ᴄʜᴀɴɴᴇʟ.\n\nᴛᴜɴᴇ ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ..."
        )
        exit()
    except Exception:
        pass

    await StreamController.decorators()
    LOGGER("Tune").info(
        "\xe1\xb4\x9b\xe1\xb4\x9c\xc9\xb4\xe1\xb4\x87\x20\xca\x99\xe1\xb4\x8f\xe1\xb4\x9b\x20\x73\xe1\xb4\x9b\xe1\xb4\x80\xca\x80\xe1\xb4\x9b\xe1\xb4\x87\xe1\xb4\x85\x20\x73\xe1\xb4\x9c\xe1\xb4\x84\xe1\xb4\x84\xe1\xb4\x87\x73\x73\xd2\x93\xe1\xb4\x9c\xca\x9f\xca\x9f\xca\x8f"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("Tune").info("sᴛᴏᴘᴘɪɴɢ ᴛᴜɴᴇ ᴠɪᴀ ᴍᴜsɪᴄ ʙᴏᴛ ...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
