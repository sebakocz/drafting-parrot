# cog for testing embeds and views

import logging

from discord import app_commands, Interaction
from discord.ext import commands

from Messages import help_msg, explain_msg


class MiscCog(commands.Cog):
    def __init__(self, bot):
        logging.info("Loading Cog: test_cog.py")
        self.bot = bot

    @app_commands.command(
        name="help", description="Your first steps with Mopping Mucus"
    )
    async def help(self, interaction: Interaction):
        message = await help_msg.get_message()
        await interaction.response.send_message(**message)

    @app_commands.command(
        name="explain", description="New to cube drafts? Click here to learn more!"
    )
    async def explain(self, interaction: Interaction):
        message = explain_msg.get_message()
        await interaction.response.send_message(**message)


async def setup(bot):  # an extension must have a setup function
    await bot.add_cog(MiscCog(bot))  # adding a cog
