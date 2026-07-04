# Lights, Fans, Discord

A monitoring system for a small office that lets anyone track lights, fans, and electricity usage through a live web dashboard and a Discord bot. Built for the Techathon Nationals preliminary round (IUT Robotics Society).

> Status: Architecture and diagrams complete. Backend, dashboard, and bot implementation in progress. This README will be updated with setup/run instructions once each component lands.

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

**Simulated Device Layer** — An asyncio background task inside the backend that owns an in-memory state for all 15 devices (status, wattage when on, room, last-changed timestamp) and advances a simulated clock so office-hours and continuous-on alert conditions can actually be demonstrated without waiting in real time.

**Backend (FastAPI)**
- REST API (`/api/status`, `/api/room/{name}`, `/api/usage`, `/api/alerts`) — used by the Discord bot and for one-off queries.
- WebSocket endpoint (`/ws/dashboard`) — pushes state changes to the web dashboard so it updates live, without a page refresh.
- Alert engine — evaluates two conditions on every simulator tick: a device still on outside 9 AM–5 PM office hours, and a room where all devices have been on continuously for more than 2 hours. Alerts are timestamped.
- Energy accumulator — integrates power draw over time to produce an estimated kWh figure for the day (used by `!usage`).
- LLM layer (optional) — turns a structured data summary into a friendlier sentence for the Discord bot, with a static-template fallback if no API key is configured, so the bot still works out of the box for anyone cloning the repo.

**Web Dashboard** — A single-page HTML/CSS/JS app served by the backend. Shows a live device status panel grouped by room, a live power meter (office-wide total plus per-room breakdown), and an active alerts panel. Connects to the backend over WebSocket, so updates appear without a manual refresh.

**Discord Bot** — Built with discord.py, running as a separate process that calls the backend's REST API (it does not import backend code directly, to keep the architecture honest to the diagram above). Commands:

| Command | What it does |
|---|---|
| `!status` | Summary of all three rooms |
| `!room <name>` | Status of one specific room |
| `!usage` | Current total wattage and today's estimated kWh |

The bot also posts proactively to a designated channel when an alert condition triggers, so the boss doesn't have to ask.

## Design Decisions

- **15 devices, not simulated hardware.** Per the problem statement's clarifications, no physical hardware is required — the office layout (2 fans + 3 lights × 3 rooms) is simulated entirely in the backend.
- **WebSocket over polling.** The dashboard requirement is explicit that updates must happen without a page refresh; WebSocket push is the direct way to satisfy that rather than short-interval polling.
- **Bot talks to the REST API, not the backend internals.** This keeps the bot and dashboard architecturally identical consumers of one API, matching the required `[Backend API] → [Web UI] && [Discord Bot]` flow, and makes it possible to run the bot on a different machine from the backend.
- **Simulated clock with adjustable speed.** Office-hours and 2-hour-continuous-on alert conditions take real hours to occur naturally. The simulator's clock can run faster than real time so these conditions can be triggered and demonstrated within a short demo video.
- **LLM responses have a fallback.** Anyone cloning this repo without an LLM API key configured should still get a working, readable bot — just with template-based phrasing instead of LLM-generated phrasing.

## Repository Structure

```
lights-fans-discord/
├── README.md
└── docs/
    └── diagrams/
        ├── system-architecture.drawio      # editable source (draw.io)
        └── lights_fans_discord.drawio.svg  # exported diagram, embedded above
```

This will grow to include `backend/`, `dashboard/`, and `bot/` directories as implementation proceeds.

## Diagramming Tool Note

The system diagram was built directly in draw.io (not Mermaid, and not auto-generated from Mermaid), per the problem statement's requirement to use a non-Mermaid diagramming tool.
