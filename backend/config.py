"""Static configuration for the office monitoring backend.

Everything that could plausibly change -- the room/device layout, wattages,
office hours, alert thresholds, and how fast the simulated clock runs -- lives
here or in an environment variable, so it is data, not code. The device count is
deliberately config-driven: the problem statement contradicts itself (15 in one
place, 18 in two others). We follow the per-room definition of 2 fans + 3 lights
per room = 15, and this file is the single place that decides that.
"""
import os

# --- Office layout -----------------------------------------------------------
ROOMS = ["Drawing Room", "Work Room 1", "Work Room 2"]
FANS_PER_ROOM = 2
LIGHTS_PER_ROOM = 3

# Rated power draw when a device is ON, in watts (the spec's own examples).
FAN_WATTS = 60
LIGHT_WATTS = 15

# --- Alert rules -------------------------------------------------------------
# Office hours are [OPEN, CLOSE) in 24h simulated local time. A device on outside
# this window is "after hours". A room whose devices are ALL on continuously for
# longer than CONTINUOUS_ON_HOURS is the second alert condition.
OFFICE_OPEN_HOUR = 9      # 9 AM
OFFICE_CLOSE_HOUR = 17    # 5 PM
CONTINUOUS_ON_HOURS = 2

# --- Simulated clock ---------------------------------------------------------
# SIM_SPEED: simulated seconds elapsed per real second. 600 => 1 real second is
# 10 simulated minutes, so a full 09:00-17:00 office day plays out in about a
# minute -- this is what makes the after-hours and continuous-on alerts
# demonstrable within a short demo instead of taking real hours.
# SIM_START_HOUR/MINUTE: the simulated time of day the backend boots at, set just
# before the office opens so the morning ramp-up is visible from the first frame.
SIM_SPEED = float(os.getenv("SIM_SPEED", "600"))
SIM_START_HOUR = int(os.getenv("SIM_START_HOUR", "8"))
SIM_START_MINUTE = int(os.getenv("SIM_START_MINUTE", "45"))

# Real seconds between simulator ticks (one state update + broadcast per tick).
TICK_SECONDS = float(os.getenv("TICK_SECONDS", "1"))

# Seed for deterministic, repeatable demo runs. Set SIM_SEED to an empty string
# for nondeterministic behaviour.
_seed = os.getenv("SIM_SEED", "42")
RANDOM_SEED = int(_seed) if _seed else None


def slugify(name: str) -> str:
    """'Work Room 1' -> 'work-room-1', used for stable device and alert ids."""
    return name.lower().replace(" ", "-")
