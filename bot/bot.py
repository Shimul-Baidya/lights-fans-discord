import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Phase 0 proof-of-concept: confirms the Discord application, token, and
# Message Content intent are correctly configured before Phase 3 adds the
# real !status / !room / !usage commands against the backend API.

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # must also be enabled in the Developer Portal, or commands are silently ignored

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    print("Hello-world bot is ready. Try !ping in a channel it can see.")


@bot.command()
async def ping(ctx):
    await ctx.send("pong — bot is alive and reading commands.")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your bot token.")
    bot.run(TOKEN)
