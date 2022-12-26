import logging

import discord
from discord.ext import commands


class NoOwnerError(commands.CommandError):
    pass


class AdminCog(commands.Cog):
    def __init__(self, bot):
        logging.info("Loading Cog: admin_cog.py")
        self.bot = bot

    async def cog_check(self, ctx):
        if not await self.bot.is_owner(ctx.author):
            raise NoOwnerError("You are not strong enough for my potions.")
        return True

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        await ctx.send(error)

    @commands.command()
    async def sync(self, ctx):
        await ctx.send("Wait for it...")
        self.bot.tree.copy_global_to(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("Synced!")

    @commands.command()
    async def clear_sync(self, ctx):
        self.bot.tree.clear_commands(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("Cleared!")

    @commands.command()
    async def ban(self, user: discord.User):
        with open("Data/banlist.txt", "a") as f:
            f.write(str(user.id) + "\n")

    @commands.command()
    async def unban(self, user: discord.User):
        with open("Data/banlist.txt", "r") as f:
            lines = f.readlines()
        with open("Data/banlist.txt", "w") as f:
            for line in lines:
                if line.strip("\n") != str(user.id):
                    f.write(line)

    @commands.command()
    async def shutdown(self, ctx):
        await ctx.send("Shutting down...")
        await self.bot.close()

async def setup(bot):  # an extension must have a setup function
    await bot.add_cog(AdminCog(bot))  # adding a cog
