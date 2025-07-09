import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall
import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.errors import FloodWait

import config
from AnonXMusic import LOGGER, app, userbot
from AnonXMusic.core.call import Anony
from AnonXMusic.misc import sudo
from AnonXMusic.plugins import ALL_MODULES
from AnonXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    # Check assistant session strings
    if not (config.STRING1 or config.STRING2 or config.STRING3 or config.STRING4 or config.STRING5):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        return

    # Load sudoers and banned users
    await sudo()
    try:
        for user_id in await get_gbanned():
            BANNED_USERS.add(user_id)
        for user_id in await get_banned_users():
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER(__name__).warning(f"Failed to load banned users: {e}")

    # Start main bot client
    try:
        await app.start()
    except FloodWait as e:
        LOGGER("AnonXMusic.app").warning(f"FloodWait: sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        await app.start()

    # Load all plugin modules
    for module in ALL_MODULES:
        importlib.import_module("AnonXMusic.plugins." + module)
    LOGGER("AnonXMusic.plugins").info("Successfully Imported Modules...")

    # Start assistant userbot client
    try:
        await userbot.start()
    except FloodWait as e:
        LOGGER("AnonXMusic.userbot").warning(f"FloodWait: sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        await userbot.start()

    # Start group call client
    try:
        await Anony.start()
    except FloodWait as e:
        LOGGER("AnonXMusic.call").warning(f"FloodWait: sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        await Anony.start()

    # Test stream to ensure VC is active
    try:
        await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("AnonXMusic").error(
            "Please turn on the videochat of your log group/channel.\nStopping Bot..."
        )
        return
    except Exception as e:
        LOGGER("AnonXMusic").warning(f"Stream test failed: {e}")

    # Load decorators
    await Anony.decorators()

    LOGGER("AnonXMusic").info(
        "AnonX Music Bot Started Successfully.\nDon't forget to visit @FallenAssociation"
    )

    # Run bot until stopped
    try:
        await idle()
    finally:
        LOGGER("AnonXMusic").info("Shutting down gracefully...")
        try:
            await app.stop()
        except Exception as e:
            LOGGER("AnonXMusic").error(f"Error while stopping app: {e}")
        try:
            await userbot.stop()
        except Exception as e:
            LOGGER("AnonXMusic").error(f"Error while stopping userbot: {e}")
        LOGGER("AnonXMusic").info("AnonX Music Bot stopped.")


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
    except Exception as e:
        import traceback
        print("Unexpected error occurred:")
        traceback.print_exc()
