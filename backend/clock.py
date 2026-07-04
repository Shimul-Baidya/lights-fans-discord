"""Simulated wall clock that can run faster than real time.

    sim_now = sim_start + (real_elapsed * speed)

Every read recomputes from a monotonic clock, so simulated time is always
internally consistent even if a tick is late, and there is no accumulated drift
to manage. Speed is fixed at construction from config/env; exposing a live speed
control is deferred to dashboard integration.
"""
import time
from datetime import datetime, timedelta


class SimClock:
    def __init__(self, sim_start: datetime, speed: float):
        self._sim_start = sim_start
        self._speed = speed
        self._real_start = time.monotonic()

    @property
    def speed(self) -> float:
        return self._speed

    def now(self) -> datetime:
        real_elapsed = time.monotonic() - self._real_start
        return self._sim_start + timedelta(seconds=real_elapsed * self._speed)
