import discord
from discord.ext import commands
from tortoise import Tortoise


class CryptoBot(commands.Bot):
    def __init__(self):
        command_prefix = "."
        intents = discord.Intents.none()
        super().__init__(command_prefix=command_prefix, intents=intents)

        self.remove_command("help")
        self.load_extension("cogs.Crypto")

    async def on_connect(self):
        await Tortoise.init(
            db_url="sqlite://main.db", modules={"models": ["utils.models"]}
        )
        await Tortoise.generate_schemas()
        return await super().on_connect()

    async def on_ready(self):
        print("Running as {} (ID: {})".format(self.user, self.user.id))

    async def on_command_error(
        self, ctx: commands.Context, exception: commands.errors.CommandError
    ) -> None:
        return  # we do not want to do anything here as we do not use message commands
