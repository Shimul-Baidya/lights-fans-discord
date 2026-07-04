"""Occupancy-based device simulator and the backend's main tick loop.

Rather than flipping devices at random (which looks fake on camera), rooms follow
an office day. Work rooms fill up when the office opens and empty at 5 PM, at
which point a device is sometimes 'forgotten' and left on -- that is what makes
the after-hours alert fire during a demo. The drawing room is a waiting area, so
it is only sporadically occupied and rarely fully lit.

Each tick: advance simulated time, update devices, accumulate energy, evaluate
alerts, and broadcast the full snapshot to every dashboard client.
"""
import asyncio
import random
from datetime import datetime

import alerts
import config
from state import office
from ws import manager

WORK_ROOMS = ["Work Room 1", "Work Room 2"]
DRAWING_ROOM = "Drawing Room"


class Simulator:
    def __init__(self):
        self.rng = random.Random(config.RANDOM_SEED)
        # The occupancy the model is currently driving each room toward. Aliased to
        # shared state so the debug endpoint (force_left_on) can pin a room and the
        # next tick won't override the forced after-hours scenario.
        self.occupied = office.occupied

    def tick(self, now: datetime) -> None:
        # Work rooms are occupied exactly during office hours. Keeping them fully
        # on across the day is deliberate: it lets the continuous-on alert fire.
        for room in WORK_ROOMS:
            target = config.OFFICE_OPEN_HOUR <= now.hour < config.OFFICE_CLOSE_HOUR
            if target != self.occupied[room]:
                self._apply(room, target, now)
                self.occupied[room] = target

        # Drawing room: sporadic waiting-area use, only during daytime.
        daytime = 8 <= now.hour < 18
        if not daytime:
            target = False
        elif self.rng.random() < 0.02:
            target = not self.occupied[DRAWING_ROOM]
        else:
            target = self.occupied[DRAWING_ROOM]
        if target != self.occupied[DRAWING_ROOM]:
            self._apply(DRAWING_ROOM, target, now)
            self.occupied[DRAWING_ROOM] = target

    def _apply(self, room: str, occupied: bool, now: datetime) -> None:
        devs = office.room_devices(room)
        if not occupied:
            # Leaving: usually everything off, but a work-room device is
            # sometimes forgotten and left on -> triggers the after-hours alert.
            forgotten = None
            if room in WORK_ROOMS and self.rng.random() < 0.6:
                forgotten = self.rng.choice(devs)
            for d in devs:
                d.set(d is forgotten, now)
        elif room == DRAWING_ROOM:
            # Waiting area: a partial, varying set of devices, rarely all of them.
            lights = [d for d in devs if d.type == "light"]
            fans = [d for d in devs if d.type == "fan"]
            on = set(self.rng.sample(lights, self.rng.randint(1, len(lights))))
            on.update(self.rng.sample(fans, self.rng.randint(0, len(fans))))
            for d in devs:
                d.set(d in on, now)
        else:  # work room arriving: everyone in, everything on.
            for d in devs:
                d.set(True, now)
        office.refresh_room_all_on(room, now)


async def run() -> None:
    """The lifespan-managed background loop. Started once at app startup."""
    sim = Simulator()
    while True:
        await asyncio.sleep(config.TICK_SECONDS)
        now = office.clock.now()
        sim.tick(now)
        office.energy.accumulate(office.total_watts(), now)
        alerts.evaluate(office, now)
        await manager.broadcast(office.snapshot().model_dump_json())
