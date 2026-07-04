import os

import aiohttp
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Discord bot: answers !status / !room / !usage by reading the backend's REST API.
# The backend is the single source of truth — the bot never computes or invents
# device state, so its answers always match the dashboard.

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Proactive alerts (bonus): numeric ID of the channel to post to. Blank/unset
# disables the feature — the commands still work. ALERT_POLL_SECONDS is how often
# the bot checks the backend for newly-triggered alerts.
_alert_channel = os.getenv("ALERT_CHANNEL_ID", "").strip()
ALERT_CHANNEL_ID = int(_alert_channel) if _alert_channel else 0
ALERT_POLL_SECONDS = float(os.getenv("ALERT_POLL_SECONDS", "10"))

# LLM phrasing (optional): if GEMINI_API_KEY is set, replies are rephrased in a
# warmer, conversational tone. On any failure the bot falls back to the template
# text, so it always answers — and always with the correct underlying data. The
# model is env-configurable; swapping providers means editing humanize() only.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash").strip()
LLM_ENABLED = bool(GEMINI_API_KEY)
LLM_INSTRUCTION = (
    "You are the friendly Discord assistant for a small office's device monitor. "
    "Reword the status below to sound like a warm, helpful coworker — human and natural, "
    "but concise, readable, and easy to scan at a glance. "
    "Keep every number, room name, wattage, and on/off state EXACTLY as given; never add, "
    "change, or drop a fact. Keep the same structure — if rooms are listed one per line, "
    "keep one room per line. No preamble or sign-off, no markdown headings; stay within a "
    "sentence or two of the original length."
)

intents = discord.Intents.default()
intents.message_content = True  # must also be enabled in the Developer Portal, or commands are silently ignored

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")  # replaced by the custom !help below


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


async def humanize(text):
    """Rephrase `text` in a warmer tone via the LLM. Falls back to `text`
    unchanged on any failure (no key, timeout, quota, error), so the bot always
    answers — and always with the correct underlying data."""
    if not LLM_ENABLED:
        return text
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": f"{LLM_INSTRUCTION}\n\nStatus:\n{text}"}]}],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 300,
            # Gemini 2.5 Flash is a "thinking" model; thinking tokens count against
            # maxOutputTokens and can truncate the reply. We're only rephrasing, so
            # turn thinking off — faster, cheaper, and no truncated output.
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params={"key": GEMINI_API_KEY}, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=6)) as resp:
                resp.raise_for_status()
                data = await resp.json()
                out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return out or text
    except Exception:
        return text


def room_body(room):
    """One room's status phrase in the spec's style, listing only what's on:
    '2 fans ON, 3 lights ON', '1 fan ON', or 'all off'."""
    fans, lights = room["fans_on"], room["lights_on"]
    parts = []
    if fans:
        parts.append(f"{fans} fan{'' if fans == 1 else 's'} ON")
    if lights:
        parts.append(f"{lights} light{'' if lights == 1 else 's'} ON")
    return ", ".join(parts) if parts else "all off"


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
    if ALERT_CHANNEL_ID:
        channel = bot.get_channel(ALERT_CHANNEL_ID)
        if channel is None:
            print(f"⚠️ ALERT_CHANNEL_ID {ALERT_CHANNEL_ID} not found — check the ID and that the bot is in that server.")
        else:
            print(f"Proactive alerts will post to #{channel.name}.")
        if not watch_alerts.is_running():
            watch_alerts.start()
    else:
        print("ALERT_CHANNEL_ID not set — proactive alerts off (commands still work).")


@bot.command()
async def ping(ctx):
    await ctx.send("pong — bot is alive and reading commands.")


@bot.command(name="status")
async def status(ctx):
    """Whole-office summary, one room per line."""
    data = await backend_get("/api/status")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    lines = [f"{room['name']}: {room_body(room)}." for room in data["rooms"]]
    on, total = data["devices_on"], data["total_devices"]
    intro = ("The office is all quiet — everything's off. 🌙" if on == 0
             else f"Here's the office right now ({on}/{total} devices on):")
    await ctx.send(await humanize(intro + "\n" + "\n".join(lines)))


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
    line = f"{data['name']}: {room_body(data)}."
    if data["all_on"]:
        line += " Everything in there is running."
    elif data["fans_on"] == 0 and data["lights_on"] == 0:
        line += " That room's completely dark right now."
    await ctx.send(await humanize(line))


@bot.command(name="usage")
async def usage(ctx):
    """Current total power and today's estimated kWh."""
    data = await backend_get("/api/usage")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    watts = data["total_watts"]
    msg = (f"Total power right now: {watts}W. "
           f"Today's estimated usage: {data['today_kwh']:.1f} kWh.")
    if watts == 0:
        msg += " Nothing's drawing power at the moment. 🌙"
    await ctx.send(await humanize(msg))


# --- Extra commands (structured output, not LLM-rephrased) -------------------
DEVICE_ICON = {"light": "💡", "fan": "🌀"}
ROOM_ICON = {"Drawing Room": "🏠"}  # work rooms fall back to 🏢


@bot.command(name="devices")
async def devices(ctx):
    """Full on/off state of every device, grouped by room."""
    data = await backend_get("/api/status")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    blocks = []
    for room in data["rooms"]:
        header = f"{ROOM_ICON.get(room['name'], '🏢')} **{room['name']}**"
        rows = [f"{DEVICE_ICON.get(d['type'], '•')} {d['name']}: {'ON' if d['on'] else 'OFF'}"
                for d in room["devices"]]
        blocks.append("\n".join([header] + rows))
    await ctx.send("📋 **Device Status**\n\n" + "\n━━━━━━━━━━━━━━\n".join(blocks))


@bot.command(name="stats")
async def stats(ctx):
    """Quick office statistics from live data."""
    data = await backend_get("/api/status")
    if data is None:
        await ctx.send(BACKEND_DOWN)
        return
    all_devices = [d for room in data["rooms"] for d in room["devices"]]
    lights = sum(1 for d in all_devices if d["type"] == "light")
    fans = sum(1 for d in all_devices if d["type"] == "fan")
    await ctx.send(
        "📈 **Statistics**\n\n"
        f"Total Devices: {data['total_devices']}\n"
        f"Lights: {lights}\n"
        f"Fans: {fans}\n"
        f"Rooms: {len(data['rooms'])}\n"
        f"Currently Active: {data['devices_on']}"
    )


@bot.command(name="help")
async def help_command(ctx):
    """List the available commands."""
    await ctx.send(
        "**Available Commands**\n\n"
        "`!status` — office summary, one line per room\n"
        "`!room <name>` — status of one room (e.g. `!room work1`)\n"
        "`!usage` — current total watts and today's estimated kWh\n"
        "`!devices` — full on/off state of every device\n"
        "`!stats` — quick office statistics"
    )


def _alert_time(a):
    """HH:MM from the alert's ISO triggered_at ('2026-07-05T11:06:..' -> '11:06')."""
    ts = a.get("triggered_at", "")
    return ts[11:16] if "T" in ts and len(ts) >= 16 else ""


def alert_line(a):
    """Friendly, proactive phrasing for a newly-triggered alert. Every alert is
    timestamped: after-hours messages already state the time ('... at HH:MM ...');
    continuous-on messages get the trigger time added here."""
    if a["type"] == "after_hours":
        return f"⚠️ Hey! {a['message']} Did someone forget to head home?"
    stamp = _alert_time(a)
    prefix = f" as of {stamp}" if stamp else ""
    return f"⚠️ Heads up{prefix} — {a['message']} Might be worth switching a few off."


_announced_alerts = set()


@tasks.loop(seconds=ALERT_POLL_SECONDS)
async def watch_alerts():
    """Poll the backend for active alerts and post each new one to the alert
    channel once. Reads the same /api/alerts the dashboard shows, so the bot's
    proactive messages never disagree with the dashboard."""
    channel = bot.get_channel(ALERT_CHANNEL_ID)
    if channel is None:
        return
    data = await backend_get("/api/alerts")
    if data is None:
        return  # backend unreachable; try again next tick
    current = {a["id"] for a in data}
    for a in data:
        if a["id"] not in _announced_alerts:
            await channel.send(await humanize(alert_line(a)))
            _announced_alerts.add(a["id"])
    # once an alert clears, forget it so a later re-trigger announces again
    _announced_alerts.intersection_update(current)


@watch_alerts.before_loop
async def _before_watch_alerts():
    await bot.wait_until_ready()


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN not set. Copy .env.example to .env and add your bot token.")
    bot.run(TOKEN)
