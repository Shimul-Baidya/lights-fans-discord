# Lights, Fans, Discord

Team **RAG_Korla** — Techathon Nationals 2026 (Preliminary Round, IUT Robotics Society).

A monitoring system for a small office that tracks lights, fans, and electricity usage through a **live web dashboard** and a **Discord bot**. Both read from one backend, so they can never disagree.

![System Architecture](docs/diagrams/system-architecture.svg)

---

## 1. Problem Statement Understanding

A small office has 3 rooms — **Drawing Room, Work Room 1, Work Room 2** — each with **2 fans + 3 lights = 15 devices**. People forget to switch devices off when they leave, and nobody notices until the electricity bill arrives. The office needs a single live view of what is on and how much power is being drawn, reachable from both a browser and Discord, plus automatic warnings when devices are left on.

Two things the system must detect on its own:
- **After-hours** — a device on outside office hours (09:00–17:00).
- **Continuous-on** — every device in a room on non-stop for more than 2 hours.

> **Device count (15, not 18):** the problem statement contradicts itself (15 in one place, 18 in two others). We follow the per-room definition — 2 fans + 3 lights × 3 rooms = **15** — and the count lives in one config file ([`backend/config.py`](backend/config.py)) so it is data, not a guess. No physical hardware is required; device state is simulated in the backend.

---

## 2. Solution Approach & Architecture

One **FastAPI backend is the single source of truth**. A simulator inside it owns the in-memory state of all 15 devices and advances a simulated clock. The dashboard and the Discord bot are both *consumers* of that backend — neither keeps its own copy of device state.

```
[Simulated Device Layer] → [Backend API] → [Web Dashboard]  &&  [Discord Bot] → User
```

- **Realtime path (WebSocket):** every simulator tick updates shared state, then the backend pushes a full snapshot over `/ws/dashboard` to every connected dashboard — no polling, no refresh.
- **On-demand path (REST):** the Discord bot and any client read `/api/*`. Same state, so the bot's answers always match the dashboard.

**Components**
| Component | Role |
|---|---|
| Simulated device layer | asyncio background task; owns 15-device state + an adjustable-speed simulated clock. Rooms follow an office day (fill at 09:00, empty at 17:00, sometimes a device is "forgotten") so alerts fire naturally. |
| Alert engine | evaluates after-hours and continuous-on (>2h) every tick; alerts are timestamped and keyed by (type, room) so they keep their trigger time until the condition clears. |
| Energy accumulator | integrates power over simulated time into today's estimated kWh; resets at simulated midnight. |
| Web dashboard | single-page HTML/CSS/JS served by the backend at `/`; connects over WebSocket for live updates. If the socket drops it **auto-falls back to a local simulation** with a clear on-screen indicator, then reconnects. |
| Discord bot | separate `discord.py` process; calls the REST API only (never imports backend code). Answers commands and posts proactive alerts. |

**Why a speed-adjustable simulated clock:** after-hours and 2-hour-continuous-on conditions take real hours to occur. The simulator's clock runs faster than real time so these alerts can be triggered and filmed inside a short demo. Speed is set by environment variable, **not** a runtime control endpoint (state stays authoritative and un-pokeable).

Editable diagram source: [`docs/diagrams/system-architecture.drawio`](docs/diagrams/system-architecture.drawio) (built in draw.io — the problem statement bans Mermaid). An ESP32/Wokwi reference circuit for Work Room 1 is in [`docs/circuit/`](docs/circuit/).

---

## 3. Technologies Used

| Layer | Technology |
|---|---|
| Language | Python 3.10+ · HTML/CSS/JavaScript (dashboard) |
| Backend | FastAPI 0.109, Uvicorn 0.27 (`[standard]` → WebSockets), Pydantic 2 |
| Bot | discord.py 2.3, aiohttp 3, python-dotenv |
| AI | Google **Gemini 2.5 Flash** (REST, inference only) — conversational rephrasing of bot replies, with a guaranteed template fallback |
| Diagram | draw.io (`.drawio` + exported `.svg`) |
| Reference circuit | Wokwi ESP32 (`docs/circuit/`) |

---

## 4. Setup & Installation

Requires Python 3.10+. Backend and bot are independent processes, each with its own virtualenv.

```bash
# from the repository root
# --- Backend ---
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
deactivate

# --- Bot ---
cd ../bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env (see §7 for the values)
deactivate
```

> Both venvs are named `venv`, so the `(venv)` shell prompt does not tell you which is active — run `which python` to confirm before installing or running.

---

## 5. How to Run

### Backend + dashboard
```bash
cd backend
source venv/bin/activate
uvicorn main:app        # add --reload while developing
```
- **Dashboard:** open <http://127.0.0.1:8000/> — live device panel, power meter, and alerts, updating over WebSocket.
- **Raw snapshot / smoke view:** <http://127.0.0.1:8000/smoke> — the exact JSON pushed over `/ws/dashboard` each tick; a debug/verification view, not the dashboard.

### Simulated clock — the speed option
Everything about the clock is controlled by environment variables at launch (no control endpoint). To make the alerts fire quickly for a demo, raise `SIM_SPEED`:

```bash
SIM_SPEED=300 uvicorn main:app          # 1 real second = 5 simulated minutes
```

| Variable | Default | Meaning |
|---|---|---|
| `SIM_SPEED` | `600` | Simulated seconds per real second. `600` ⇒ a full 09:00–17:00 day in ~1 min. Higher = faster. |
| `SIM_START_HOUR` | `8` | Simulated hour the backend boots at. |
| `SIM_START_MINUTE` | `45` | Simulated minute at boot (default 08:45 shows the morning ramp-up). |
| `TICK_SECONDS` | `1` | Real seconds between state updates/broadcasts. |
| `SIM_SEED` | `42` | RNG seed for repeatable demos; empty = nondeterministic. |

Example — start just before closing so the after-hours alert appears within seconds:
```bash
SIM_SPEED=600 SIM_START_HOUR=16 SIM_START_MINUTE=50 uvicorn main:app
```

### Discord bot
The backend should be running first (the bot reads its REST API).
```bash
cd bot
source venv/bin/activate
python3 bot.py
```

One-time Discord setup:
1. <https://discord.com/developers/applications> → **New Application** → **Bot** → **Reset Token**, paste it into `bot/.env` as `DISCORD_TOKEN`.
2. On the **Bot** tab, enable **Message Content Intent** — without this the bot connects but ignores every command.
3. **OAuth2 → URL Generator** → scope `bot`, permission `Send Messages` → open the URL to invite it to your server.
4. (Optional) For proactive alerts, enable **Developer Mode** (Settings → Advanced), right-click your alerts channel → **Copy Channel ID**, and set `ALERT_CHANNEL_ID` in `.env`.
5. Run `python3 bot.py`, then type `!status` in a channel the bot can see.

**Commands**
| Command | Response |
|---|---|
| `!status` | Whole-office summary, one line per room |
| `!room <name>` | One room's status — accepts aliases (`work1`, `wr2`, `drawing`, `Work Room 1`, …) |
| `!usage` | Current total watts + today's estimated kWh |
| `!devices` | Full on/off state of every device, grouped by room |
| `!stats` | Device/room counts and how many are on |
| `!help` | Lists the commands |
| `!ping` | Liveness check |

When `ALERT_CHANNEL_ID` is set, the bot also polls `/api/alerts` every `ALERT_POLL_SECONDS` (default 10) and posts each **new** alert to that channel once, timestamped.

---

## 6. API Endpoints Documentation

Base URL `http://127.0.0.1:8000`. All REST responses are JSON.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/status` | All rooms + devices, per-room and office totals |
| GET | `/api/room/{name}` | One room; `{name}` is case-insensitive, display name or slug (`Work Room 1` / `work-room-1`); 404 if unknown |
| GET | `/api/usage` | Total watts, per-room watts, today's kWh, simulated time |
| GET | `/api/alerts` | Currently active alerts, oldest first |
| WS | `/ws/dashboard` | Full snapshot pushed on every tick (used by the dashboard) |
| GET | `/` | Web dashboard (static SPA) |
| GET | `/smoke` | Raw snapshot debug viewer |

Example — `GET /api/status` (trimmed):
```json
{
  "rooms": [
    { "name": "Work Room 1", "total_watts": 105, "fans_on": 1, "lights_on": 3, "all_on": false,
      "devices": [
        { "id": "work-room-1-light-1", "name": "Light 1", "type": "light", "room": "Work Room 1",
          "on": true, "watts": 15, "rated_watts": 15, "last_changed": "2026-07-04T09:00:00" }
      ] }
  ],
  "total_watts": 75, "total_devices": 15, "devices_on": 2
}
```

Example — `GET /api/alerts`:
```json
[{ "id": "after_hours:Work Room 1", "type": "after_hours", "room": "Work Room 1",
   "message": "Work Room 1 still has 1 fan on at 17:07 (outside office hours).",
   "triggered_at": "2026-07-04T17:07:00", "active": true }]
```
`/api/usage` → `{ "total_watts", "per_room_watts": {room: watts}, "today_kwh", "sim_time" }`. The `/ws/dashboard` frame wraps all of it: `{ "sim_time", "speed", "office", "usage", "alerts" }`.

---

## 7. AI Integration Details

- **Model:** Google **Gemini 2.5 Flash** (`gemini-2.5-flash`), called over the Generative Language REST API from the Discord bot.
- **What it does:** rephrases the bot's replies and proactive alerts into a warm, conversational tone. It is a presentation layer only — it **never** decides device state or invents facts. The prompt instructs it to keep every number, room name, wattage, and on/off state exactly as given; all data comes from the backend.
- **No training / fine-tuning:** inference only against the hosted model. `thinkingConfig.thinkingBudget` is set to `0` (rephrasing needs no reasoning tokens — faster, cheaper, no truncation).
- **Guaranteed fallback:** on any failure — no key, timeout, quota/rate-limit (HTTP 429), or error — `humanize()` returns the deterministic template text unchanged. The bot always answers, always with correct data. (Verified: with quota available the reply is rephrased; when the free tier is rate-limited the template is returned verbatim.)
- **Configurable, not hardcoded:** provider/model and key come from the environment.

`bot/.env` values:
```ini
DISCORD_TOKEN=your_bot_token_here
BACKEND_URL=http://127.0.0.1:8000     # only change if the bot runs on another machine
ALERT_CHANNEL_ID=                     # numeric channel ID for proactive alerts; blank = off
GEMINI_API_KEY=                       # blank = templates only (get one at aistudio.google.com/apikey)
LLM_MODEL=gemini-2.5-flash
```

---

## Repository Structure

```
.
├── README.md
├── backend/
│   ├── main.py            # FastAPI app: lifespan simulator task, REST router, /ws/dashboard, /, /smoke
│   ├── config.py          # room/device layout, wattages, office hours, alert thresholds, sim-clock env vars
│   ├── models.py          # Pydantic response contract shared by dashboard and bot
│   ├── clock.py           # SimClock — adjustable-speed simulated time
│   ├── state.py           # OfficeState — the single shared source of truth
│   ├── energy.py          # EnergyAccumulator — integrates power into today's kWh
│   ├── alerts.py          # alert engine — after-hours and continuous-on (>2h)
│   ├── simulator.py       # occupancy model + tick loop (advance, update, accumulate, evaluate, broadcast)
│   ├── ws.py              # ConnectionManager — WebSocket registry + broadcast
│   ├── api.py             # REST endpoints
│   ├── static/index.html  # /smoke raw snapshot viewer (debug)
│   └── requirements.txt
├── bot/
│   ├── bot.py             # Discord bot: commands, proactive alerts, Gemini rephrasing + fallback
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── index.html         # live dashboard (served at /), with WebSocket + local-sim fallback
│   └── *.png              # dashboard assets
└── docs/
    ├── diagrams/          # system-architecture.drawio (+ exported .svg)
    └── circuit/           # Wokwi ESP32 reference circuit for Work Room 1
```
