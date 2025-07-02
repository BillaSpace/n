from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []

class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="AnonXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="AnonXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="AnonXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="AnonXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="AnonXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info("Starting Assistants...")

        if config.STRING1:
            await self.one.start()
            try:
                await self.one.join_chat("BillaSpace")
                await self.one.join_chat("BillaCore")
            except:
                pass
            assistants.append(1)
            try:
                await self.one.send_message(config.LOGGER_ID, "Assistant1 Started join - @BillaSpace")
            except:
                LOGGER(__name__).error(
                    "Assistant Account 1 has failed to access the log group. Make sure it is added and promoted as admin!"
                )
                exit()
            self.one.id = (await self.one.get_me()).id
            self.one.name = (await self.one.get_me()).mention
            self.one.username = (await self.one.get_me()).username
            assistantids.append(self.one.id)
            LOGGER(__name__).info(f"Assistant One started as {self.one.name}")

        if config.STRING2:
            await self.two.start()
            try:
                await self.two.join_chat("BillaSpace")
                await self.two.join_chat("BillaCore")
            except:
                pass
            assistants.append(2)
            try:
                await self.two.send_message(config.LOGGER_ID, "Assistant2 Started join - @BillaSpace")
            except:
                LOGGER(__name__).error(
                    "Assistant Account 2 has failed to access the log group. Make sure it is added and promoted as admin!"
                )
                exit()
            self.two.id = (await self.two.get_me()).id
            self.two.name = (await self.two.get_me()).mention
            self.two.username = (await self.two.get_me()).username
            assistantids.append(self.two.id)
            LOGGER(__name__).info(f"Assistant Two started as {self.two.name}")

        if config.STRING3:
            await self.three.start()
            try:
                await self.three.join_chat("BillaSpace")
                await self.three.join_chat("BillaCore")
            except:
                pass
            assistants.append(3)
            try:
                await self.three.send_message(config.LOGGER_ID, "Assistant3 Started join - @BillaSpace")
            except:
                LOGGER(__name__).error(
                    "Assistant Account 3 has failed to access the log group. Make sure it is added and promoted as admin!"
                )
                exit()
            self.three.id = (await self.three.get_me()).id
            self.three.name = (await self.three.get_me()).mention
            self.three.username = (await self.three.get_me()).username
            assistantids.append(self.three.id)
            LOGGER(__name__).info(f"Assistant Three started as {self.three.name}")

        if config.STRING4:
            await self.four.start()
            try:
                await self.four.join_chat("BillaSpace")
                await self.four.join_chat("BillaCore")
            except:
                pass
            assistants.append(4)
            try:
                await self.four.send_message(config.LOGGER_ID, "Assistant4 Started join - @BillaSpace")
            except:
                LOGGER(__name__).error(
                    "Assistant Account 4 has failed to access the log group. Make sure it is added and promoted as admin!"
                )
                exit()
            self.four.id = (await self.four.get_me()).id
            self.four.name = (await self.four.get_me()).mention
            self.four.username = (await self.four.get_me()).username
            assistantids.append(self.four.id)
            LOGGER(__name__).info(f"Assistant Four started as {self.four.name}")

        if config.STRING5:
            await self.five.start()
            try:
                await self.five.join_chat("BillaSpace")
                await self.five.join_chat("BillaCore")
            except:
                pass
            assistants.append(5)
            try:
                await self.five.send_message(config.LOGGER_ID, "Assistant5 Started join - @BillaSpace")
            except:
                LOGGER(__name__).error(
                    "Assistant Account 5 has failed to access the log group. Make sure it is added and promoted as admin!"
                )
                exit()
            self.five.id = (await self.five.get_me()).id
            self.five.name = (await self.five.get_me()).mention
            self.five.username = (await self.five.get_me()).username
            assistantids.append(self.five.id)
            LOGGER(__name__).info(f"Assistant Five started as {self.five.name}")

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except Exception as e:
            LOGGER(__name__).error(f"Error while stopping assistants: {e}")