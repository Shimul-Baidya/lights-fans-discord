"""REST API consumed by the Discord bot (and any one-off client). Every handler
reads straight from the shared office state, so the bot's answers always match
what the dashboard is showing at the same moment.
"""
from fastapi import APIRouter, HTTPException

from models import Alert, OfficeStatus, RoomStatus, Usage
from state import office

router = APIRouter(prefix="/api")


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
