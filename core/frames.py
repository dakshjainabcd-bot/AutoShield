"""The frame record used everywhere in the Python side of AutoShield.

A frame is (t, can_id, dlc, data):
  t       time in seconds (float)
  can_id  11-bit identifier (int)
  dlc     number of data bytes (int, 8 for the whole catalogue)
  data    the payload bytes (bytes). It defaults to empty so that tiny hand-made
          test traces can be written as Frame(0.1, 0x100, 8).

Because Frame is a NamedTuple, f[0], f[1], f[2] also work, exactly like the
(time, id, dlc) tuples in the roadmap.
"""
from typing import NamedTuple


class Frame(NamedTuple):
    t: float
    can_id: int
    dlc: int
    data: bytes = b""
