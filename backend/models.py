"""Pydantic response models: the JSON contract the web dashboard and Discord bot
consume. These shapes are frozen -- later phases read them as-is, so changing a
field here is an API change, not a refactor. Keeping them in one place is what
guarantees the dashboard and the bot see identical data.
"""
from datetime import datetime

from pydantic import BaseModel


class Device(BaseModel):
    id: str
    name: str
    type: str            # "fan" | "light"
    room: str
    on: bool
    watts: int           # current draw: rated when on, 0 when off
    rated_watts: int
    last_changed: datetime


class RoomStatus(BaseModel):
    name: str
    devices: list[Device]
    total_watts: int
    fans_on: int
    lights_on: int
    all_on: bool


class OfficeStatus(BaseModel):
    rooms: list[RoomStatus]
    total_watts: int
    total_devices: int
    devices_on: int


class Usage(BaseModel):
    total_watts: int
    per_room_watts: dict[str, int]
    today_kwh: float
    sim_time: datetime


class Alert(BaseModel):
    id: str
    type: str            # "after_hours" | "continuous_on"
    room: str
    message: str
    triggered_at: datetime
    active: bool = True


class DashboardSnapshot(BaseModel):
    """The full payload pushed over /ws/dashboard on every tick."""
    sim_time: datetime
    speed: float
    office: OfficeStatus
    usage: Usage
    alerts: list[Alert]
