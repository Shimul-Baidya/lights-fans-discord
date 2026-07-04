"""WebSocket connection registry + broadcast. Generalizes the Phase 0 broadcast
loop's dead-socket cleanup into one place, so any part of the backend can push a
snapshot to every connected dashboard client.

`manager` at the bottom is the one shared instance the app imports.
"""
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    @property
    def count(self) -> int:
        return len(self._connections)

    async def send(self, ws: WebSocket, message: str) -> None:
        await ws.send_text(message)

    async def broadcast(self, message: str) -> None:
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._connections.difference_update(dead)


manager = ConnectionManager()
