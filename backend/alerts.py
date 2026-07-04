"""Alert engine. Evaluated once per simulator tick against the shared office
state. Two conditions, both taken directly from the spec:

  after_hours   -- a device is on outside office hours (09:00-17:00).
  continuous_on -- every device in a room has been on continuously for > 2 hours.

Alerts are keyed by (type, room) so an alert keeps its original trigger
timestamp while its condition holds, and disappears when the condition clears.
"""
from datetime import datetime, timedelta

import config
from models import Alert
from state import OfficeState


def evaluate(state: OfficeState, now: datetime) -> None:
    """Recompute the active alert set in place on `state`."""
    active: dict[str, Alert] = {}
    after_hours = not (config.OFFICE_OPEN_HOUR <= now.hour < config.OFFICE_CLOSE_HOUR)

    for room in config.ROOMS:
        on_devs = [d for d in state.room_devices(room) if d.on]

        # after_hours: any device on while the office is closed.
        if after_hours and on_devs:
            fans = sum(1 for d in on_devs if d.type == "fan")
            lights = sum(1 for d in on_devs if d.type == "light")
            aid = f"after_hours:{room}"
            msg = f"{room} still has {_phrase(fans, lights)} on at {now:%H:%M} (outside office hours)."
            active[aid] = _carry(state, aid, "after_hours", room, now, msg)

        # continuous_on: all devices in the room on for longer than the threshold.
        since = state.room_all_on_since.get(room)
        if since is not None and now - since >= timedelta(hours=config.CONTINUOUS_ON_HOURS):
            hours = (now - since).total_seconds() / 3600.0
            aid = f"continuous_on:{room}"
            msg = f"{room} has had all devices on for {hours:.1f}h continuously."
            active[aid] = _carry(state, aid, "continuous_on", room, now, msg)

    state.active_alerts = active


def _carry(state: OfficeState, aid: str, type: str, room: str,
           now: datetime, message: str) -> Alert:
    """Build the alert, preserving the trigger time if it was already active."""
    existing = state.active_alerts.get(aid)
    triggered_at = existing.triggered_at if existing else now
    return Alert(id=aid, type=type, room=room, message=message,
                 triggered_at=triggered_at, active=True)


def _phrase(fans: int, lights: int) -> str:
    parts = []
    if fans:
        parts.append(f"{fans} fan" + ("" if fans == 1 else "s"))
    if lights:
        parts.append(f"{lights} light" + ("" if lights == 1 else "s"))
    return " and ".join(parts) if parts else "devices"
