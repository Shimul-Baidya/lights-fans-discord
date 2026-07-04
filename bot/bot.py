import os

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Discord bot: answers !status / !room / !usage by reading the backend's REST API.
# The backend is the single source of truth — the bot never computes or invents
# device state, so its answers always match the dashboard.

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

intents = discord.Intents.default()
intents.message_content = True  # must also be enabled in the Developer Portal, or commands are silently ignored

bot = commands.Bot(command_prefix="!", intents=intents)


async def backend_get(path):
    """GET JSON from the backend REST API. Returns the parsed JSON, or None if the
    backend is unreachable. Because the backend is the single source of truth, when
    the bot can't read it, it says so rather than making anything up."""
    url = f"{BACKEND_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception:
        return None


def room_body(room):
    """One room's status phrase, matching the spec exactly:
    '2 fans ON, 3 lights ON'  or  'all off'."""
    fans, lights = room["fans_on"], room["lights_on"]
    if fans == 0 and lights == 0:
        return "all off"
    return f"{fans} fan{'' if fans == 1 else 's'} ON, {lights} light{'' if lights == 1 else 's'} ON"


# User-typed room names -> the office's canonical room names, so the boss can type
# "work1", "Work Room 1", "work-room-1", "drawing", etc. (spec example: !room work1).
ROOM_ALIASES = {
    "drawingroom": "Drawing Room", "drawing": "Drawing Room", "dr": "Drawing Room",
    "workroom1": "Work Room 1", "work1": "Work Room 1", "wr1": "Work Room 1", "w1": "Work Room 1",
    "workroom2": "Work Room 2", "work2": "Work Room 2", "wr2": "Work Room 2", "w2": "Work Room 2",
}


def resolve_room(name):
    """Normalize a typed room name to a canonical room, or None if unrecognized."""
    key = name.lower().replace(" ", "").replace("-", "").replace("_", "")
    return ROOM_ALIASES.get(key)


BACKEND_DOWN = "⚠️ I can't reach the office monitor right now — is the backend running?"


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    print(f"Reading office data from {BACKEND_URL}. Try !status in a channel it can see.")


@bot.command()
async def ping(ctx):
    await ctx.send("pong — bot is alive and reading commands.")


@bot.command(name="status")
async def status(ctx):
    """Whole-office summary, one room per sentence."""
    data = await backend_get("/api/status")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    sentences = [f"{room['name']}: {room_body(room)}" for room in data["rooms"]]
    await ctx.send(". ".join(sentences) + ".")


@bot.command(name="room")
async def room(ctx, *, name: str = ""):
    """Status of one room. Accepts aliases like 'work1' or 'drawing'."""
    if not name.strip():
        await ctx.send("Which room? Try `!room work1`, `!room work2`, or `!room drawing`.")
        return
    canonical = resolve_room(name)
    if canonical is None:
        await ctx.send(f'I don\'t know a room called "{name.strip()}". '
                       f"Try: Drawing Room, Work Room 1, or Work Room 2.")
        return
    slug = canonical.lower().replace(" ", "-")
    data = await backend_get(f"/api/room/{slug}")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    await ctx.send(f"{data['name']}: {room_body(data)}")


@bot.command(name="usage")
async def usage(ctx):
    """Current total power and today's estimated kWh."""
    data = await backend_get("/api/usage")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    await ctx.send(f"Total power right now: {data['total_watts']}W. "
                   f"Today's estimated usage: {data['today_kwh']:.1f} kWh.")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your bot token.")
    bot.run(TOKEN)
