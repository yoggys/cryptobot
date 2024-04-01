import datetime
from io import BytesIO
from os import getenv
from random import randint

import discord
import matplotlib.pyplot as plt
import pandas as pd
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from tortoise import transactions

from utils.client import CryptoBot
from utils.models import CryptoHistoryModel, CryptoModel, EconomyModel


async def get_available_tags(ctx: discord.AutocompleteContext):
    return [
        model.tag.upper()
        for model in await CryptoModel.filter()
        if ctx.options.get("tag").lower() in model.tag.lower()
    ]


class Crypto(commands.Cog):
    def __init__(self, client):
        self.client: CryptoBot = client

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.crypto_random.is_running():
            self.crypto_random.start()

    @tasks.loop(seconds=float(getenv("CRYPTO_RANDOM_INTERVAL")))
    async def crypto_random(self):
        async with transactions.in_transaction():
            for crypto in await CryptoModel.all():
                await CryptoHistoryModel.create(crypto_id=crypto.id, price=crypto.price)
                crypto.price += randint(-crypto.changes, crypto.changes)
                # make sure the price is not negative and >= 1
                if crypto.price < 1:
                    crypto.price = 1
                await crypto.save()

    @crypto_random.before_loop
    async def before_schedule_tasks(self):
        await self.client.wait_until_ready()

    @commands.slash_command(name="info", description="Check bot info.")
    async def info(
        self,
        ctx: discord.ApplicationContext,
    ):
        embed = discord.Embed(color=0x66C4D8)
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/727659575196647425/820054574068531200/cryptoend.gif"
        )
        await ctx.respond(embed=embed)

    admin = SlashCommandGroup(
        "admin",
        checks=[commands.guild_only()],
        default_permissions=discord.Permissions(administrator=True),
    )

    @admin.command(name="create", description="Create a new crypto.")
    async def create(
        self,
        ctx: discord.ApplicationContext,
        tag: discord.Option(
            str, description="Tag of the crypto (max 3 chars).", max_length=3
        ),
        name: discord.Option(
            str, description="Name of the crypto (max 32 chars).", max_length=32
        ),
        price: discord.Option(int, description="Starting price of the crypto."),
        changes: discord.Option(int, description="Change rate of the crypto."),
    ):
        if await CryptoModel.get_or_none(tag=tag.upper()):
            return await ctx.respond(
                f"❌ Crypto with tag ` {tag.upper()} ` already exists.", ephemeral=True
            )
        await CryptoModel.create(
            tag=tag.upper(), price=price, name=name, changes=changes
        )
        await ctx.respond(
            f"✅ Crypto with tag `{tag.upper()}` created successfully with price {price}."
        )

    @admin.command(name="remove", description="Remove a crypto.")
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        tag: discord.Option(str, description="Name of the crypto."),
    ):
        if model := await CryptoModel.get_or_none(tag=tag.upper()):
            await model.delete()
            await ctx.respond(
                f"✅ Crypto with tag `{tag.upper()}` deleted successfully."
            )
        else:
            await ctx.respond(
                f"❌ Crypto with tag ` {tag.upper()} ` does not exists.", ephemeral=True
            )

    crypto = SlashCommandGroup("crypto", checks=[commands.guild_only()])

    @crypto.command(name="balance", description="Check someone balance.")
    async def balance(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(discord.Member, "The user to check.") = None,
    ):
        user = user or ctx.author
        if model := await EconomyModel.get_or_none(user_id=user.id):
            balance = model.balance
            crypto_balance = model.crypto_balance

            embed = discord.Embed(
                color=0x66C4D8, description=f"> Balance: ` {balance}$ `"
            )
            embed.set_author(name=user.name, icon_url=user.display_avatar)

            for name, value in crypto_balance.items():
                embed.add_field(name=name, value=f"` {value} `")

            await ctx.respond(embed=embed)
        else:
            await ctx.respond(
                f"❌ {user.mention} do not have any balance yet.", ephemeral=True
            )

    @crypto.command(name="buy", description="Buy crypto.")
    async def buy(
        self,
        ctx: discord.ApplicationContext,
        tag: discord.Option(
            str, description="The crypto tag.", autocomplete=get_available_tags
        ),
        amount: discord.Option(int, description="The amount of crypto to buy."),
    ):
        if amount < 1:
            return await ctx.respond(
                "❌ You must buy at least 1 crypto.", ephemeral=True
            )

        crypto = await CryptoModel.get_or_none(tag=tag.upper())
        if crypto is None:
            return await ctx.respond("❌ Invalid crypto tag.", ephemeral=True)

        user, _ = await EconomyModel.get_or_create(user_id=ctx.author.id)

        if amount * crypto.price > user.balance:
            return await ctx.respond(
                "❌ You do not have enough money to buy this crypto.", ephemeral=True
            )

        user.balance -= amount * crypto.price
        user.crypto_balance[tag.upper()] = (
            user.crypto_balance.get(tag.upper(), 0) + amount
        )
        await user.save()

        await ctx.respond(
            "✅ You have bought ` {} ` of ` {} ` for ` {}$ `.".format(
                amount, crypto.tag, amount * crypto.price
            )
        )

    @crypto.command(name="sell", description="Sell crypto.")
    async def sell(
        self,
        ctx: discord.ApplicationContext,
        tag: discord.Option(
            str, description="The crypto tag.", autocomplete=get_available_tags
        ),
        amount: discord.Option(int, description="The amount of crypto to sell."),
    ):
        if amount < 1:
            return await ctx.respond(
                "❌ You must sell at least 1 crypto.", ephemeral=True
            )

        crypto = await CryptoModel.get_or_none(tag=tag.upper())
        if crypto is None:
            return await ctx.respond("❌ Invalid crypto tag.", ephemeral=True)

        user, _ = await EconomyModel.get_or_create(user_id=ctx.author.id)

        if amount > user.crypto_balance.get(tag.upper(), 0):
            return await ctx.respond(
                f"❌ You do not have enough `{tag.upper()}` to sell.", ephemeral=True
            )

        user.balance += amount * crypto.price
        user.crypto_balance[tag.upper()] -= amount
        await user.save()

        await ctx.respond(
            "✅ You have sold ` {} ` of ` {} ` for ` {}$ `.".format(
                amount, crypto.tag, amount * crypto.price
            )
        )

    @crypto.command(
        name="graph", description="Graph of crypto in given period of time."
    )
    async def graph(
        self,
        ctx: discord.ApplicationContext,
        tag: discord.Option(
            str, description="The crypto tag.", autocomplete=get_available_tags
        ),
        period: discord.Option(
            str,
            description="The period to check the price for.",
            choices=["hour", "day", "week"],
        ),
    ):
        crypto = await CryptoModel.get_or_none(tag=tag.upper())
        if crypto is None:
            return await ctx.respond("❌ Invalid crypto tag.", ephemeral=True)
        await ctx.defer()

        prices = (
            await CryptoHistoryModel.filter(
                crypto_id=crypto.id,
                created_at__gte=discord.utils.utcnow()
                - datetime.timedelta(**{period + "s": 1}),
            )
            .order_by("-created_at")
            .all()
        )

        if prices[-1].price != prices[0].price:
            symbol = "↑" if prices[0].price > prices[-1].price else "↓"
        else:
            symbol = "="

        percent = abs((prices[-1].price - prices[0].price) * 100 / prices[-1].price)
        title = "{} ({}/\$) - {} changes      {}\$      {}{:.2f}%".format(
            crypto.name, crypto.tag, period, crypto.price, symbol, percent
        )

        plt.clf()
        plt.style.use("dark_background")
        for param in ["text.color", "axes.labelcolor", "xtick.color", "ytick.color"]:
            plt.rcParams[param] = "0.9"
        for param in ["figure.facecolor", "axes.facecolor", "savefig.facecolor"]:
            plt.rcParams[param] = "#212946"
        colors = [
            "#08F7FE",
            "#FE53BB",
            "#F5D300",
            "#00ff41",
        ]

        fig, ax = plt.subplots()
        df = pd.DataFrame(
            {crypto.tag: [price.price for price in prices]},
            index=[price.created_at for price in prices],
        )

        minimal_value = int(df.min().iloc[0]) - 1
        maximal_value = int(df.max().iloc[0]) + 1

        df.plot(
            color=colors,
            ax=ax,
            xticks=[],
            yticks=[minimal_value, maximal_value],
            title=title,
        )
        n_shades = 10
        diff_linewidth = 1.05
        alpha_value = 0.3 / n_shades
        for n in range(1, n_shades + 1):
            df.plot(
                linewidth=2 + (diff_linewidth * n),
                alpha=alpha_value,
                legend=False,
                ax=ax,
                color=colors,
            )
        for key, color in zip(df, colors):
            ax.fill_between(x=df.index, y1=df[key].values, color=color, alpha=0.1)
        ax.grid(color="#2A3459")
        ax.set_xlim(min(df.index), max(df.index))
        ax.set_ylim(
            minimal_value - (maximal_value - minimal_value) * 0.1,
            maximal_value + (maximal_value - minimal_value) * 0.1,
        )

        graph = BytesIO()
        plt.savefig(graph, format="png")
        plt.clf()
        plt.close()
        graph.seek(0)
        await ctx.respond(file=discord.File(graph, filename="graph.png"))


def setup(client):
    client.add_cog(Crypto(client))
