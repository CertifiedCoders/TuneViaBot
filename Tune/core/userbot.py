# Authored By Certified Coders © 2025
from pyrogram import Client

import config

from Tune.logging import LOGGER

assistants = []
assistantids = []

GROUPS_TO_JOIN = [
    "CertifiedDiscussion",
    "CertifiedCoders",
    "CertifiedCodes",
    "CertifiedDevs",
    "CertifiedNetwork",
]


def get_available_sessions():
    sessions = [
        config.STRING1,
        config.STRING2,
        config.STRING3,
        config.STRING4,
        config.STRING5,
    ]
    return [(idx, session) for idx, session in enumerate(sessions, start=1) if session]


def get_session_count():
    return len(get_available_sessions())


class Userbot:
    def __init__(self):
        available_sessions = get_available_sessions()
        self.session_count = len(available_sessions)
        self.assistants = []
        self._assistant_dict = {}
        max_sessions = 5
        
        self._assistants_list = [None] * max_sessions
        
        for idx, session_string in available_sessions:
            client = Client(
                f"TuneAssis{idx}",
                config.API_ID,
                config.API_HASH,
                session_string=str(session_string),
                no_updates=True,
            )
            self.assistants.append((idx, client))
            self._assistant_dict[idx] = client
            self._assistants_list[idx - 1] = client
        
        assistant_names = ["one", "two", "three", "four", "five"]
        for i in range(max_sessions):
            setattr(self, assistant_names[i], self._assistants_list[i])
    
    def get_assistant(self, index: int):
        return self._assistant_dict.get(index)
    
    def get_assistants_list(self):
        return [client for client in self._assistants_list if client is not None]
    
    def get_assistant_indices(self):
        return [idx for idx, _ in self.assistants]

    async def start_assistant(self, client: Client, index: int):
        if index not in self._assistant_dict:
            return

        try:
            await client.start()
            for group in GROUPS_TO_JOIN:
                try:
                    await client.join_chat(group)
                except Exception:
                    pass

            assistants.append(index)

            try:
                await client.send_message(
                    config.LOGGER_ID, f"Tune's Assistant {index} Started"
                )
            except Exception:
                LOGGER(__name__).error(
                    f"Assistant {index} can't access the log group. Check permissions!"
                )
                exit()

            me = await client.get_me()
            client.id, client.name, client.username = me.id, me.first_name, me.username
            assistantids.append(me.id)

            LOGGER(__name__).info(f"Assistant {index} Started as {client.name}")

        except Exception as e:
            LOGGER(__name__).error(f"Failed to start Assistant {index}: {e}")

    async def start(self):
        LOGGER(__name__).info(
            f"Starting Tune's Assistants... (Found {self.session_count} active assistant{'s' if self.session_count != 1 else ''})"
        )
        for idx, client in self.assistants:
            await self.start_assistant(client, idx)

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        for idx, client in self.assistants:
            try:
                await client.stop()
            except Exception as e:
                LOGGER(__name__).error(f"Error stopping Assistant {idx}: {e}")
