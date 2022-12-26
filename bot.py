# Dear programmer:
# When I wrote this code, only god, and I knew how it worked
# Now, only god knows it!
#
# Therefore, if you are trying to optimize this,
# and it fails (most surely)
# please increase this counter as a warning for the next person:
#
# total_hours_wasted_here = 254

import os
import logging

from dotenv import load_dotenv

import discord
from discord.ext import commands

from Database import database

import asyncio
import platform


# Extra Cases ---------------------------------------------------------------

# prevent event loop is closed error
# https://stackoverflow.com/questions/45600579/asyncio-event-loop-is-closed-when-getting-loop
from Database.Models.draft import Draft

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# prevent voice client warning
discord.VoiceClient.warn_nacl = False

# ---------------------------------------------------------------------------

discord.utils.setup_logging()

load_dotenv()

is_dev = os.getenv("IS_DEV") == "True"


class MyBot(commands.Bot):
    async def setup_hook(self):

        await database.init()

        await bot.load_extension("Cogs.admin_cog")
        await bot.load_extension("Cogs.draft_cog")

        if is_dev:
            await bot.load_extension("Cogs.test_cog")

    async def close(self):
        logging.info("Closing discord bot...")
        await database.Tortoise.close_connections()
        await super().close()


intents = discord.Intents.all()

bot = MyBot(
    command_prefix="!",
    intents=intents,
)


@bot.event
async def on_ready():
    logging.info(f"{bot.user} has connected to Discord!")


@bot.check_once
def exclude_banned_users(ctx):
    # previously would prevent cmds from running if banlist.txt doesn't exist
    # 'x+' mode raises FileExistsError if the file already exists
    try:
        open("Data/banlist.txt", "x+")
    except FileExistsError:
        with open("Data/banlist.txt", "r") as f:
            for line in f.readlines():
                if line.strip("\n") == str(ctx.author.id):
                    return False
    return True


bot.run(os.getenv("DISCORD_TOKEN"), log_handler=None)
