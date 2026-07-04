"""Accumulates energy use over simulated time to produce 'today's estimated kWh'
for the !usage command.

Energy is the integral of power over time. Each tick we add

    watts * (sim_seconds_elapsed / 3600) / 1000   [kWh]

using the *simulated* elapsed time, so clock acceleration is accounted for
correctly. The running total resets when the simulated calendar day rolls over.
"""
from datetime import datetime


class EnergyAccumulator:
    def __init__(self, now: datetime):
        self.today_kwh = 0.0
        self._last_time = now
        self._last_date = now.date()

    def accumulate(self, total_watts: int, now: datetime) -> None:
        if now.date() != self._last_date:
            # Simulated midnight: start a fresh day's total.
            self.today_kwh = 0.0
            self._last_date = now.date()
            self._last_time = now
            return
        elapsed_sim_seconds = (now - self._last_time).total_seconds()
        if elapsed_sim_seconds > 0:
            self.today_kwh += total_watts * (elapsed_sim_seconds / 3600.0) / 1000.0
        self._last_time = now
