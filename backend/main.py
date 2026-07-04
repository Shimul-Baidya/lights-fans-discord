"""FastAPI application. Wires the simulator loop into the app lifespan -- the
same lifespan pattern the Phase 0 proof-of-concept used -- and exposes the REST
API plus the /ws/dashboard WebSocket that pushes a full state snapshot on every
simulator tick.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

import simulator
from api import router as api_router
from state import office
from ws import manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(simulator.run())
    yield
    task.cancel()


app = FastAPI(title="Lights, Fans, Discord — Backend", lifespan=lifespan)
app.include_router(api_router)

INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text()


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    # Push the current snapshot immediately so a newly connected client isn't
    # blank until the next tick.
    await manager.send(websocket, office.snapshot().model_dump_json())
    try:
        while True:
            # We don't expect inbound messages; this await just keeps the socket
            # open and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
