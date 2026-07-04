"""The single source of truth: in-memory office state that both the dashboard
(via WebSocket) and the Discord bot (via REST) read from. Nothing else in the
system holds a copy of device state.

`office` at the bottom is the one shared instance the rest of the backend imports.
"""
from datetime import datetime, time as timeofday

import config
from clock import SimClock
from energy import EnergyAccumulator
from models import Alert, DashboardSnapshot, Device, OfficeStatus, RoomStatus, Usage


def _initial_sim_start() -> datetime:
    """Today's date at the configured start-of-day time."""
    today = datetime.now().date()
    return datetime.combine(today, timeofday(config.SIM_START_HOUR, config.SIM_START_MINUTE))


class DeviceState:
    """Mutable device record. Serialized to the immutable `Device` model on read."""

    def __init__(self, id: str, name: str, type: str, room: str,
                 rated_watts: int, last_changed: datetime):
        self.id = id
        self.name = name
        self.type = type
        self.room = room
        self.rated_watts = rated_watts
        self.on = False
        self.last_changed = last_changed

    @property
    def watts(self) -> int:
        return self.rated_watts if self.on else 0

    def set(self, on: bool, now: datetime) -> bool:
        """Set on/off state. Returns True only if the state actually changed."""
        if self.on == on:
            return False
        self.on = on
        self.last_changed = now
        return True

    def to_model(self) -> Device:
        return Device(
            id=self.id, name=self.name, type=self.type, room=self.room,
            on=self.on, watts=self.watts, rated_watts=self.rated_watts,
            last_changed=self.last_changed,
        )


class OfficeState:
    def __init__(self):
        self.clock = SimClock(_initial_sim_start(), config.SIM_SPEED)
        now = self.clock.now()
        self.devices: list[DeviceState] = self._build_devices(now)
        self.energy = EnergyAccumulator(now)
        # Alert-engine bookkeeping, kept here so state stays the single source of
        # truth. active_alerts is keyed by alert id; room_all_on_since records
        # when each room most recently became fully on (None if it isn't).
        self.active_alerts: dict[str, Alert] = {}
        self.room_all_on_since: dict[str, datetime | None] = {r: None for r in config.ROOMS}
        # Which rooms the occupancy simulator is currently driving 'occupied'.
        # Held on shared state (not private to the simulator) so the debug endpoint
        # can pin a room's occupancy when forcing an after-hours scenario. See
        # force_left_on() and simulator.Simulator.
        self.occupied: dict[str, bool] = {r: False for r in config.ROOMS}

    def _build_devices(self, now: datetime) -> list[DeviceState]:
        devices: list[DeviceState] = []
        for room in config.ROOMS:
            slug = config.slugify(room)
            for i in range(1, config.LIGHTS_PER_ROOM + 1):
                devices.append(DeviceState(f"{slug}-light-{i}", f"Light {i}",
                                           "light", room, config.LIGHT_WATTS, now))
            for i in range(1, config.FANS_PER_ROOM + 1):
                devices.append(DeviceState(f"{slug}-fan-{i}", f"Fan {i}",
                                           "fan", room, config.FAN_WATTS, now))
        return devices

    # --- queries -------------------------------------------------------------
    def room_devices(self, room: str) -> list[DeviceState]:
        return [d for d in self.devices if d.room == room]

    def find_room(self, name: str) -> str | None:
        """Resolve a user-supplied room name (case-insensitive, slug or display)."""
        q = name.strip().lower()
        for r in config.ROOMS:
            if q == r.lower() or q == config.slugify(r):
                return r
        return None

    def total_watts(self) -> int:
        return sum(d.watts for d in self.devices)

    def per_room_watts(self) -> dict[str, int]:
        return {r: sum(d.watts for d in self.room_devices(r)) for r in config.ROOMS}

    def refresh_room_all_on(self, room: str, now: datetime) -> None:
        """Maintain the continuous-on tracker after a room's devices change."""
        all_on = all(d.on for d in self.room_devices(room))
        if all_on and self.room_all_on_since[room] is None:
            self.room_all_on_since[room] = now
        elif not all_on:
            self.room_all_on_since[room] = None

    def force_left_on(self, room: str, now: datetime, count: int = 2) -> None:
        """Debug affordance: simulate devices 'left on after hours'. Switches the
        room off, turns `count` of its devices back on, and pins the room as
        unoccupied so the simulator's next tick won't sweep them off again. The
        after-hours alert then fires from the real device state + the (jumped)
        clock -- no alert is fabricated."""
        devs = self.room_devices(room)
        for d in devs:
            d.set(False, now)
        for d in devs[:count]:
            d.set(True, now)
        self.occupied[room] = False
        self.refresh_room_all_on(room, now)

    # --- serialization to the API contract -----------------------------------
    def room_status(self, room: str) -> RoomStatus:
        devs = self.room_devices(room)
        return RoomStatus(
            name=room,
            devices=[d.to_model() for d in devs],
            total_watts=sum(d.watts for d in devs),
            fans_on=sum(1 for d in devs if d.type == "fan" and d.on),
            lights_on=sum(1 for d in devs if d.type == "light" and d.on),
            all_on=all(d.on for d in devs),
        )

    def office_status(self) -> OfficeStatus:
        rooms = [self.room_status(r) for r in config.ROOMS]
        return OfficeStatus(
            rooms=rooms,
            total_watts=self.total_watts(),
            total_devices=len(self.devices),
            devices_on=sum(1 for d in self.devices if d.on),
        )

    def usage(self) -> Usage:
        return Usage(
            total_watts=self.total_watts(),
            per_room_watts=self.per_room_watts(),
            today_kwh=round(self.energy.today_kwh, 3),
            sim_time=self.clock.now(),
        )

    def alerts(self) -> list[Alert]:
        return sorted(self.active_alerts.values(), key=lambda a: a.triggered_at)

    def snapshot(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            sim_time=self.clock.now(),
            speed=self.clock.speed,
            office=self.office_status(),
            usage=self.usage(),
            alerts=self.alerts(),
        )


# The one shared state instance for the whole backend.
office = OfficeState()
