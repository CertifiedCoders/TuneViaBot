# Authored By Certified Coders © 2025
import socket
import time

import heroku3
from pyrogram import filters

import config
from Tune.core.mongo import mongodb

from Tune.logging import LOGGER

SUDOERS = filters.user()

HAPP = None
_boot_ = time.time()


def is_heroku():
    return "heroku" in socket.getfqdn()


XCB = [
    "/",
    "@",
    ".",
    "com",
    ":",
    "git",
    "heroku",
    "push",
    str(config.HEROKU_API_KEY),
    "https",
    str(config.HEROKU_APP_NAME),
    "HEAD",
    "master",
]


def dbb():
    """
    Initialize the in-memory playback database.
    """
    global db
    db = {}
    LOGGER(__name__).info("Pʟᴀʏʙᴀᴄᴋ ᴅᴀᴛᴀʙᴀsᴇ ɪɴɪᴛɪᴀʟɪᴢᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ. 🍂")


def set_current_message(chat_id: int, mystic, markup: str) -> None:
    """
    Safely attach the current message object and markup tag to the head
    of the playback queue for a chat. This is concurrency-safe against
    the queue being cleared or emptied in another task.
    """
    try:
        queue = db.get(chat_id)
        if not queue:
            return
        queue[0]["mystic"] = mystic
        queue[0]["markup"] = markup
    except Exception:
        # If the queue vanishes between the length check and assignment,
        # just ignore – it means playback was cleared concurrently.
        return


async def sudo():
    global SUDOERS
    SUDOERS.add(config.OWNER_ID)
    sudoersdb = mongodb.sudoers
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    sudoers = [] if not sudoers else sudoers["sudoers"]
    if config.OWNER_ID not in sudoers:
        sudoers.append(config.OWNER_ID)
        await sudoersdb.update_one(
            {"sudo": "sudo"},
            {"$set": {"sudoers": sudoers}},
            upsert=True,
        )
    if sudoers:
        for user_id in sudoers:
            SUDOERS.add(user_id)
    LOGGER(__name__).info(f"sᴜᴅᴏ ᴜsᴇʀs ᴅᴏɴᴇ..")


def heroku():
    global HAPP
    if is_heroku:
        if config.HEROKU_API_KEY and config.HEROKU_APP_NAME:
            try:
                Heroku = heroku3.from_key(config.HEROKU_API_KEY)
                HAPP = Heroku.app(config.HEROKU_APP_NAME)
                LOGGER(__name__).info(f"ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ᴄᴏɴғɪɢᴜʀᴇᴅ..")
            except BaseException:
                LOGGER(__name__).warning(
                    f"ʏᴏᴜ sʜᴏᴜʟᴅ ʜᴀᴠᴇ ɴᴏᴛ ғɪʟʟᴇᴅ ʜᴇʀᴏᴋᴜ ᴀᴘᴘ ɴᴀᴍᴇ ᴏʀ ᴀᴘɪ ᴋᴇʏ ᴄᴏʀʀᴇᴄᴛʟʏ ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ɪᴛ..."
                )
