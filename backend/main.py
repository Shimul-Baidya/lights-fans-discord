import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# Phase 0 proof-of-concept: confirms the FastAPI WebSocket broadcast mechanism
# works end to end (server push -> browser update, no polling, no refresh)
# before Phase 1 wires it to real device state.

active_connections: set[WebSocket] = set()
counter = 0


async def broadcast_loop():
    global counter
    while True:
        await asyncio.sleep(1)
        counter += 1
        payload = json.dumps({
            "counter": counter,
            "server_time": datetime.now().strftime("%H:%M:%S"),
            "connected_clients": len(active_connections),
        })
        dead = set()
        for ws in active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        active_connections.difference_update(dead)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text()


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.discard(websocket)
