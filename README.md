# Lights, Fans, Discord

A monitoring system for a small office that lets anyone track lights, fans, and electricity usage through a live web dashboard and a Discord bot. Built for the Techathon Nationals preliminary round (IUT Robotics Society).

> Status: Architecture and diagrams complete. Backend core (device registry, simulated clock, occupancy simulator, energy accumulator, alert engine, REST API, WebSocket broadcast) is implemented and verified. Dashboard and Discord bot implementation in progress.

## The Problem

The office has 3 rooms — Drawing Room, Work Room 1, Work Room 2 — each with 2 fans and 3 lights (15 devices total). People forget to turn devices off when they leave, and nobody notices until the electricity bill arrives. This project gives the office a single live view of device state and power draw, accessible from both a browser and Discord.

## Office Layout

| Room | Fans | Lights | Usage |
|---|---|---|---|
| Drawing Room | 2 | 3 | Waiting area |
| Work Room 1 | 2 | 3 | Employees |
| Work Room 2 | 2 | 3 | Employees |

**Total: 6 fans + 9 lights = 15 devices.**

No physical hardware is used. Device state is simulated by the backend and is dynamic — it changes over time to mimic a real office day (devices turning on in the morning, staying on through work hours, occasionally being left on past 5 PM).

## Architecture

![System Architecture](docs/diagrams/lights_fans_discord.drawio.svg)

Source (editable in [draw.io](https://app.diagrams.net)): [`docs/diagrams/system-architecture.drawio`](docs/diagrams/system-architecture.drawio)

The system has one backend that acts as the single source of truth. Both the web dashboard and the Discord bot read from it — neither interface stores or computes its own copy of device state, so they can never show different answers to the same question.

```
[Simulated Device Layer] → [Backend API] → [Web UI] && [Discord Bot] → User
```

Realtime path: the simulator updates the shared device state on every tick; the backend broadcasts that state over WebSocket to every connected dashboard client; the dashboard applies the update immediately, with no polling and no page refresh. This path is marked in bold blue on the diagram. REST reads, alert evaluation, and energy accumulation branch off the same shared state but are on-demand, not push-based, and are marked in gray.

**Simulated Device Layer** — An asyncio background task inside the backend that owns an in-memory state for all 15 devices (status, wattage when on, room, last-changed timestamp) and advances a simulated clock so office-hours and continuous-on alert conditions can actually be demonstrated without waiting in real time.

**Backend (FastAPI)**
- REST API (`/api/status`, `/api/room/{name}`, `/api/usage`, `/api/alerts`) — used by the Discord bot and for one-off queries.
- WebSocket endpoint (`/ws/dashboard`) — broadcasts every device state change to all connected dashboard clients as it happens.
- Alert engine — evaluates two conditions on every simulator tick: a device still on outside 9 AM–5 PM office hours, and a room where all devices have been on continuously for more than 2 hours. Alerts are timestamped.
- Energy accumulator — integrates power draw over time to produce an estimated kWh figure for the day (used by `!usage`).

**Web Dashboard** — A single-page HTML/CSS/JS app served by the backend. Shows a live device status panel grouped by room, a live power meter (office-wide total plus per-room breakdown), and an active alerts panel. Connects to the backend over WebSocket, so updates appear without a manual refresh.

**Discord Bot** — Built with discord.py, running as a separate process that calls the backend's REST API (it does not import backend code directly, to keep the architecture honest to the diagram above). Commands:

| Command | What it does |
|---|---|
| `!status` | Summary of all three rooms |
| `!room <name>` | Status of one specific room |
| `!usage` | Current total wattage and today's estimated kWh |

The bot also posts proactively to a designated channel when an alert condition triggers, so the boss doesn't have to ask.

Response phrasing is produced by a configurable LLM provider, selected via environment variable rather than hardcoded into the bot. If the provider call fails, times out, or returns a quota error, the bot falls back to a template-based response built from the same data. Both paths return through the bot, so it always answers.

## Design Decisions

- **15 devices, not simulated hardware.** Per the problem statement's clarifications, no physical hardware is required — the office layout (2 fans + 3 lights × 3 rooms) is simulated entirely in the backend.
- **WebSocket over polling.** The dashboard requirement is explicit that updates must happen without a page refresh; WebSocket push is the direct way to satisfy that rather than short-interval polling.
- **Bot talks to the REST API, not the backend internals.** This keeps the bot and dashboard architecturally identical consumers of one API, matching the required `[Backend API] → [Web UI] && [Discord Bot]` flow, and makes it possible to run the bot on a different machine from the backend.
- **Simulated clock with adjustable speed.** Office-hours and 2-hour-continuous-on alert conditions take real hours to occur naturally. The simulator's clock can run faster than real time so these conditions can be triggered and demonstrated within a short demo video.
- **LLM provider is configurable, not hardcoded.** The bot calls whichever provider is set via environment variable and falls back to template responses on failure, timeout, or quota exhaustion. The provider can be swapped without changing the bot's architecture, and the bot never fails to respond.

## Repository Structure

```
lights-fans-discord/
├── README.md
├── backend/
│   ├── main.py              # FastAPI app: lifespan-managed simulator task, REST router, /ws/dashboard
│   ├── config.py            # device registry, wattages, office hours, alert thresholds, sim clock speed
│   ├── models.py            # Pydantic response contract (Device, RoomStatus, Usage, Alert, DashboardSnapshot)
│   ├── clock.py             # SimClock — adjustable-speed simulated time
│   ├── state.py             # OfficeState — the single shared source of truth
│   ├── energy.py            # EnergyAccumulator — integrates power draw into today's kWh
│   ├── alerts.py            # alert engine — after-hours and continuous-on (>2h) conditions
│   ├── simulator.py         # occupancy model + the tick loop (advance, update, accumulate, evaluate, broadcast)
│   ├── ws.py                # ConnectionManager — WebSocket registry and broadcast
│   ├── api.py               # REST endpoints: /api/status, /api/room/{name}, /api/usage, /api/alerts
│   ├── static/index.html    # raw snapshot viewer for /ws/dashboard — a smoke test, not the dashboard
│   └── requirements.txt
├── bot/
│   ├── bot.py                # hello-world Discord bot (!ping), correct intents
│   ├── requirements.txt
│   └── .env.example
└── docs/
    └── diagrams/
        ├── system-architecture.drawio      # editable source (draw.io)
        └── lights_fans_discord.drawio.svg  # exported diagram, embedded above
```

`bot/` currently holds a Phase 0 proof-of-concept — it confirms the Discord bot's connection and intents work before Phase 3 builds the real commands on top. The dashboard lives in its own not-yet-created directory (`frontend/`) built against the same `/ws/dashboard` contract `backend/static/index.html` exercises.

## Running the Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` in a browser to see the raw JSON pushed over `/ws/dashboard` on every simulator tick (sim time, per-room device states, total watts, active alerts) — a verification view, not the final dashboard. Or query the REST API directly:

```bash
curl http://127.0.0.1:8000/api/status
curl http://127.0.0.1:8000/api/room/Work%20Room%201
curl http://127.0.0.1:8000/api/usage
curl http://127.0.0.1:8000/api/alerts
```

The simulated clock's speed and start time are set via environment variables (`SIM_SPEED`, `SIM_START_HOUR`, `SIM_START_MINUTE` in `config.py`) rather than a runtime control endpoint — office-hours and continuous-on alert conditions that take real hours to occur naturally can be sped through in a minute or two, which is what makes them demonstrable in a short demo video.

## Running the Bot Prototype

`bot/` is still the Phase 0 hello-world bot (`!ping` only) — the real `!status`/`!room`/`!usage` commands against the backend's REST API are Phase 3, not yet built.

```bash
cd bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env and paste in a real bot token
python3 bot.py
```

Requires a Discord application with a bot user:
1. [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot tab → Reset Token, copy it into `.env`.
2. On the same Bot tab, enable **Message Content Intent** — without this the bot connects but silently ignores every command.
3. OAuth2 → URL Generator → scope `bot`, permission `Send Messages` → open the generated URL to invite it to a test server.
4. Run `python3 bot.py`, then type `!ping` in a channel the bot can see; it should reply "pong — bot is alive and reading commands."

## Diagramming Tool Note

The system diagram was built directly in draw.io (not Mermaid, and not auto-generated from Mermaid), per the problem statement's requirement to use a non-Mermaid diagramming tool.
