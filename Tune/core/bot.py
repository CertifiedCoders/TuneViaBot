from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus
import config
import sys

from Tune.logging import LOGGER


class JARVIS(Client):
    def __init__(self):
        LOGGER(__name__).info("Starting Bot...")
        super().__init__(
            name="TuneViaBot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            sleep_threshold=240,
            max_concurrent_transmissions=7,
            workers=50,
        )

    async def start(self):
        await super().start()

        try:
            bot_info = await self.get_me()
            self.username = bot_info.username
            self.id = bot_info.id
            self.name = f"{bot_info.first_name} {bot_info.last_name or ''}".strip()
            self.mention = bot_info.mention

            await self.send_message(
                chat_id=config.LOGGER_ID,
                text=(
                    f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                    f"ɪᴅ : <code>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                ),
            )

            chat_member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if chat_member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error(
                    "❌ Bot is not an admin in the log group/channel. Please promote it."
                )
                sys.exit()

        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error(
                "❌ Invalid LOGGER_ID. Make sure your bot is added to the log group/channel."
            )
            sys.exit()
        except Exception as ex:
            LOGGER(__name__).error(
                f"❌ Failed to access log group/channel.\nReason: {type(ex).__name__} - {ex}"
            )
            sys.exit()

        LOGGER(__name__).info(f"Tune Music Bot Started as {self.name}")
