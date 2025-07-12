from pyrogram import Client
from pyrogram.errors.exceptions.flood_420 import FloodWait
import config
from ..logging import LOGGER
import asyncio

assistants = []
assistantids = []

log = LOGGER(__name__)


class Userbot(Client):
    def __init__(self):
        self.clients = []

        # Define session strings
        session_strings = [
            config.STRING1,
            config.STRING2,
            config.STRING3,
            config.STRING4,
            config.STRING5,
        ]

        # Create clients and add legacy attributes
        for idx, string in enumerate(session_strings, start=1):
            if string:
                client = Client(
                    name=f"AnonXAss{idx}",
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=str(string),
                    no_updates=True,
                )
                self.clients.append((client, string, idx))
                # Add backward-compatible attribute: one, two, etc.
                setattr(self, f"{['one','two','three','four','five'][idx-1]}", client)

    async def start_assistant(self, client, assistant_num):
        async def try_start(client, max_retries=3):
            for attempt in range(max_retries):
                try:
                    await client.start()
                    return True
                except FloodWait as e:
                    wait_time = e.value + 1
                    log.warning(f"FloodWait: Waiting {wait_time}s for assistant {assistant_num}")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    log.error(f"Error starting assistant {assistant_num}: {e}")
                    return False
            log.error(f"Assistant {assistant_num} failed after {max_retries} retries.")
            return False

        if not await try_start(client):
            return False

        # Join support chats
        try:
            await client.join_chat("BillaSpace")
            await client.join_chat("BillaCore")
        except Exception:
            pass

        assistants.append(assistant_num)

        # Try sending log
        try:
            await client.send_message(config.LOGGER_ID, f"Assistant {assistant_num} Started - Joined @BillaSpace")
        except Exception:
            log.error(f"Assistant {assistant_num} couldn't access LOGGER_ID. Add it and promote to admin.")
            return False

        # Get assistant info
        try:
            me = await client.get_me()
            client.id = me.id
            client.name = me.mention
            client.username = me.username
            assistantids.append(me.id)
            log.info(f"Assistant {assistant_num} started as {client.name}")
            return True
        except FloodWait as e:
            wait_time = e.value + 1
            log.warning(f"FloodWait during get_me on assistant {assistant_num}. Waiting {wait_time}s.")
            await asyncio.sleep(wait_time)
            return False
        except Exception as e:
            log.error(f"Failed to fetch info for assistant {assistant_num}: {e}")
            return False

    async def start(self):
        log.info("Starting Assistants...")
        for client, string, i in self.clients:
            if string:
                await self.start_assistant(client, i)
                await asyncio.sleep(2)

    async def stop(self):
        log.info("Stopping Assistants...")
        for client, string, i in self.clients:
            if string:
                try:
                    await client.stop()
                except Exception as e:
                    log.error(f"Error stopping assistant {i}: {e}")
