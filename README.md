# Lights, Fans, Discord

A monitoring system for a small office that lets anyone track lights, fans, and electricity usage through a live web dashboard and a Discord bot. Built for the Techathon Nationals preliminary round (IUT Robotics Society).

> Status: Architecture and diagrams complete. Backend core (device registry, simulated clock, occupancy simulator, energy accumulator, alert engine, REST API, WebSocket broadcast) is implemented and verified. The live web dashboard (`frontend/`) is implemented and wired to the backend. Discord bot implementation in progress.

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
- Debug trigger (`POST /api/debug/trigger-alert`) — testing-only endpoint that fast-forwards the simulated clock past 5 PM so the after-hours alert can be demonstrated on demand. See [Triggering the Alerts on Demand](#triggering-the-alerts-on-demand-for-judging).

**Web Dashboard** — A single-page HTML/CSS/JS app served by the backend. Shows a live device status panel grouped by room, a live power meter (office-wide total plus per-room breakdown), and an active alerts panel. Connects to the backend over WebSocket, so updates appear without a manual refresh.

**Discord Bot** — Built with discord.py, running as a separate process that calls the backend's REST API (it does not import backend code directly, to keep the architecture honest to the diagram above). Commands:

| Command | What it does |
|---|---|
| `!status` | Summary of all three rooms |
| `!room <name>` | Status of one specific room |
| `!usage` | Current total wattage and today's estimated kWh |

The bot also posts proactively to a designated channel when an alert condition triggers, so the boss doesn't have to ask.

Response phrasing is produced by a configurable LLM provider, selected via environment variable rather than hardcoded into the bot. If the provider call fails, times out, or returns a quota error, the bot falls back to a template-based response built from the same data. Both paths return through the bot, so it always answers.

## Deliverables

The preliminary round asks for five deliverables. Where each one lives in this repository:

| # | Deliverable | Status | Location |
|---|---|---|---|
| 1 | High-level system diagram (non-Mermaid) | Done | [`docs/diagrams/`](docs/diagrams/) — embedded under [Architecture](#architecture) |
| 2 | Hardware / electrical schematic (Wokwi) | Done | [`docs/circuit/`](docs/circuit/) — see [Hardware / Circuit Schematic](#hardware--circuit-schematic) |
| 3 | Simulated device data — status, watts, room, last-changed; dynamic | Done | `backend/` — occupancy simulator over one shared in-memory state |
| 4 | Real-time web dashboard — device panel, power meter, alerts | Done | [`frontend/`](frontend/) — served by the backend at `/` |
| 5 | Discord bot — `!status`, `!room`, `!usage` | Phase 0 prototype | [`bot/`](bot/) — `!ping` only; the real commands are Phase 3 |

Bonus items attempted: the dashboard renders the top-view office layout with **lights that glow when ON and fans that animate when running**, and the alert engine plus a proactive Discord post cover the "device left on after hours" scenario.

## Design Decisions

- **15 devices, not simulated hardware.** Per the problem statement's clarifications, no physical hardware is required — the office layout (2 fans + 3 lights × 3 rooms) is simulated entirely in the backend.
- **WebSocket over polling.** The dashboard requirement is explicit that updates must happen without a page refresh; WebSocket push is the direct way to satisfy that rather than short-interval polling.
- **Bot talks to the REST API, not the backend internals.** This keeps the bot and dashboard architecturally identical consumers of one API, matching the required `[Backend API] → [Web UI] && [Discord Bot]` flow, and makes it possible to run the bot on a different machine from the backend.
- **Simulated clock with adjustable speed.** Office-hours and 2-hour-continuous-on alert conditions take real hours to occur naturally. The simulator's clock can run faster than real time so these conditions can be triggered and demonstrated within a short demo video.
- **LLM provider is configurable, not hardcoded.** The bot calls whichever provider is set via environment variable and falls back to template responses on failure, timeout, or quota exhaustion. The provider can be swapped without changing the bot's architecture, and the bot never fails to respond.

## Hardware / Circuit Schematic

Deliverable 2 is a representative sensing circuit for one room (Work Room 1: 2 fans + 3 lights), built in [Wokwi](https://wokwi.com). Per the problem statement, wiring every device isn't required — one room is enough to demonstrate the design, and no real hardware is used.

The full rationale — why the ESP32 never touches mains power, how slide switches and LEDs stand in for a relay/current-sensor signal and the microcontroller's own state indicator, the GPIO pin map, and the per-device wiring pattern — is documented in [`docs/circuit/README.md`](docs/circuit/README.md), alongside the [`sketch.ino`](docs/circuit/sketch.ino) firmware and the Wokwi [`diagram.json`](docs/circuit/diagram.json). The sketch marks exactly where a real deployment would replace its serial print with a WiFi call to the backend's device-state endpoint.

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
│   ├── api.py               # REST endpoints: /api/status, /api/room/{name}, /api/usage, /api/alerts, /api/debug/trigger-alert
│   ├── static/index.html    # raw snapshot viewer for /ws/dashboard (served at /smoke) — a smoke test, not the dashboard
│   └── requirements.txt
├── frontend/
│   ├── index.html            # the dashboard — single-page app, served by the backend at /
│   ├── icons8-energy-saving-64.png
│   └── layout.png            # top-view office layout reference
├── bot/
│   ├── bot.py                # hello-world Discord bot (!ping), correct intents
│   ├── requirements.txt
│   └── .env.example
└── docs/
    ├── diagrams/
    │   ├── system-architecture.drawio      # editable source (draw.io)
    │   └── lights_fans_discord.drawio.svg  # exported diagram, embedded above
    └── circuit/                            # Wokwi sensing circuit (deliverable 2)
        ├── README.md                       # design rationale, pin map, wiring pattern
        ├── sketch.ino                      # ESP32 firmware
        └── diagram.json                    # Wokwi schematic
```

`bot/` currently holds a Phase 0 proof-of-concept — it confirms the Discord bot's connection and intents work before Phase 3 builds the real `!status`/`!room`/`!usage` commands on top. `frontend/` holds the live dashboard, built against the same `/ws/dashboard` contract `backend/static/index.html` exercises as a raw smoke view.

## Running the Backend & Dashboard

The backend serves the API and the dashboard together, so one command brings up the whole web side:

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open **`http://127.0.0.1:8000`** — that is the live dashboard: device status grouped by room, an office-wide plus per-room power meter, an active-alerts panel, and the top-view floor plan with glowing lights and animated fans. It updates over `/ws/dashboard` with no page refresh. Two supporting views are also available:

- **`http://127.0.0.1:8000/smoke`** — the raw JSON snapshot pushed on every simulator tick, kept for debugging.
- The REST API, queryable directly (this is the same data the Discord bot reads):

```bash
curl http://127.0.0.1:8000/api/status
curl http://127.0.0.1:8000/api/room/Work%20Room%201
curl http://127.0.0.1:8000/api/usage
curl http://127.0.0.1:8000/api/alerts
```

The simulated clock's speed and start time are set via environment variables (`SIM_SPEED`, `SIM_START_HOUR`, `SIM_START_MINUTE` in `config.py`). Office-hours and continuous-on alert conditions that would take real hours to occur are sped through in a minute or two — with the defaults the after-hours alert fires on its own about 50 seconds after startup. To surface it instantly during a walkthrough, see [Triggering the Alerts on Demand](#triggering-the-alerts-on-demand-for-judging) below.

## Triggering the Alerts on Demand (for judging)

Both alert conditions appear on their own shortly after startup — with the default clock speed the simulated day reaches 5 PM in about 50 seconds (after-hours alert), and a work room crosses the 2-hour continuous-on threshold within about 15 seconds. No interaction is needed for the alerts panel to populate.

For a live walkthrough where waiting is awkward, the dashboard includes a small **Simulation Debugger** so the after-hours scenario can be shown immediately.

**Open it** on the dashboard: press **Ctrl / ⌘ + Shift + D**, or click the faint version tag in the bottom-right corner. Then click **Trigger 5 PM Scenario** — an after-hours alert for Work Room 2 appears within a second and the header clock jumps to 17:05.

**What it does — and why it isn't faking data.** The button calls one backend endpoint, `POST /api/debug/trigger-alert`, which *only fast-forwards the simulated clock* past closing time and leaves two devices on in one room. The alert itself is still computed by the normal alert engine from the real device state — nothing is hardcoded or fabricated. It is exactly what happens naturally when the simulated day reaches 5 PM, just triggered on demand instead of on a timer.

> **This is a testing / demo affordance, not a product feature.** In a real deployment the clock would track wall-clock time and this endpoint would be disabled. It exists so the alert path can be demonstrated and tested in seconds instead of waiting for the office day to play out, and it is deliberately tucked behind a keyboard shortcut so it never distracts from the live dashboard.

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
