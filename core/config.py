"""Load the shared configuration (core/config.json).

One file holds every threshold, so the simulator, the Python reference and
(in Phase 5) the firmware header all use the same numbers.
All values are STARTING values to be tuned from data, not measured results.
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config(path=None):
    """Return the configuration as a dict. Pass a path to use another file."""
    with open(path or CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)
