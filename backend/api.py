"""REST API consumed by the Discord bot (and any one-off client). Every handler
reads straight from the shared office state, so the bot's answers always match
what the dashboard is showing at the same moment.
"""
from datetime import timedelta

from fastapi import APIRouter, HTTPException

import alerts
import config
from models import Alert, OfficeStatus, RoomStatus, Usage
from state import office
from ws import manager

router = APIRouter(prefix="/api")

# Room the debug trigger leaves devices on in, to demonstrate the after-hours alert.
DEBUG_ROOM = "Work Room 2"


@router.get("/status", response_model=OfficeStatus)
def get_status():
    """Whole-office device status, grouped by room."""
    return office.office_status()


@router.get("/room/{name}", response_model=RoomStatus)
def get_room(name: str):
    """Status of one room. Name is case-insensitive ('Work Room 1' or 'work-room-1')."""
    room = office.find_room(name)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Unknown room: {name!r}")
    return office.room_status(room)


@router.get("/usage", response_model=Usage)
def get_usage():
    """Current total watts, per-room breakdown, and today's estimated kWh."""
    return office.usage()


@router.get("/alerts", response_model=list[Alert])
def get_alerts():
    """Currently active alerts, oldest first."""
    return office.alerts()


@router.post("/debug/trigger-alert")
async def debug_trigger_alert():
    """Developer tooling. Fast-forwards the simulated clock just past office close
    and leaves a couple of devices on in one room, so the after-hours alert can be
    demonstrated on demand instead of waiting for the sim day to reach 17:00. The
    alert is still produced by the normal engine from real device state -- nothing
    is faked; only the clock is advanced.

    Driven by the dashboard's Simulation Debugger (Ctrl/Cmd+Shift+D)."""
    now = office.clock.now()
    target = now.replace(hour=config.OFFICE_CLOSE_HOUR, minute=5,
                         second=0, microsecond=0)
    if target <= now:                      # already past 17:05 -> next sim day
        target += timedelta(days=1)
    office.clock.jump_to(target)
    office.force_left_on(DEBUG_ROOM, target, count=2)
    alerts.evaluate(office, target)
    # Push the new snapshot immediately so the dashboard updates without waiting
    # for the next simulator tick.
    await manager.broadcast(office.snapshot().model_dump_json())
    return {"ok": True, "sim_time": target.isoformat(), "room": DEBUG_ROOM}
