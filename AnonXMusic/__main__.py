import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from AnonXMusic import LOGGER, app, userbot
from AnonXMusic.core.call import Anony
from AnonXMusic.misc import sudo
from AnonXMusic.plugins import ALL_MODULES
from AnonXMusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant String Sessions or client variables are not defined, exiting...")
        exit()

    await sudo()

    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except Exception as e:
        LOGGER(__name__).warning(f"Error loading banned users: {e}")

    await app.start()

    for module in ALL_MODULES:
        if not module.strip():
            continue
        try:
            importlib.import_module(f"AnonXMusic.plugins.{module}")
            LOGGER("AnonXMusic.plugins").info(f"✅ Loaded module: {module}")
        except Exception as e:
            LOGGER("AnonXMusic.plugins").error(f"❌ Failed to import module '{module}': {e}")

    LOGGER("AnonXMusic.plugins").info("✅ Successfully imported all plugin modules.")

    await userbot.start()
    await Anony.start()

    try:
        await Anony.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("AnonXMusic").error(
            "❌ Please turn on the videochat of your log group/channel.\nStopping Bot..."
        )
        exit()
    except Exception as e:
        LOGGER("AnonXMusic").warning(f"⚠️ Stream startup failed: {e}")

    await Anony.decorators()

    LOGGER("AnonXMusic").info(
        "✅ AnonX Music Bot Started Successfully.\nVisit @FallenAssociation"
    )

    await idle()
    await app.stop()
    await userbot.stop()

    LOGGER("AnonXMusic").info("👋 Stopping AnonX Music Bot...")


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        print("🛑 Bot stopped manually.")
    except Exception:
        import traceback
        print("❌ Unexpected error occurred:")
        traceback.print_exc()
