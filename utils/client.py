import discord


class CryptoBot(discord.Bot):
    def __init__(self):
        intents = discord.Intents.none()
        super().__init__(intents=intents)

        self.remove_command("help")
        self.load_extension("cogs.Crypto")

    async def on_ready(self):
        print("Running as {} (ID: {})".format(self.user, self.user.id))
