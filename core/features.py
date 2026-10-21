"""Feature extraction (roadmap step 1.6). The six features and their ORDER are
part of the contract (contracts/telemetry_schema.md).

A window is the last W seconds of frames, half-open: t_end - W <= t < t_end.
"""
from collections import Counter

import numpy as np

from core import catalogue as C

FEATURE_NAMES = [
    "total_rate", "dominance",
    "hb_gap_mean_ms", "hb_gap_std_ms",
    "imu_gap_mean_ms", "imu_gap_std_ms",
]


def select_window(frames, t_end, W=1.0):
    """Frames with t_end - W <= t < t_end."""
    lo = t_end - W
    return [f for f in frames if lo <= f[0] < t_end]


def _gaps_ms(window, can_id, W):
    # Sort the times of this ID: with jitter, list order is not always time order.
    ts = sorted(f[0] for f in window if f[1] == can_id)
    if len(ts) < 2:
        # Design choice: a silent ID gives a very unusual vector, not an error.
        return W * 1000.0, 0.0
    g = np.diff(ts) * 1000.0
    return float(g.mean()), float(g.std())


def features_from_window(window, W=1.0):
    """The six features from frames that are already inside the window."""
    n = len(window)
    total_rate = n / W
    if n:
        dominance = max(Counter(f[1] for f in window).values()) / n
    else:
        dominance = 0.0
    hb_mean, hb_std = _gaps_ms(window, C.ID_NODE_HB, W)
    imu_mean, imu_std = _gaps_ms(window, C.ID_NODE_IMU, W)
    return [float(total_rate), float(dominance), hb_mean, hb_std, imu_mean, imu_std]


def window_features(frames, t_end, W=1.0):
    """Roadmap-compatible helper: select the window, then compute the features."""
    return features_from_window(select_window(frames, t_end, W), W)


def frame_bits(dlc):
    """Bits per classic CAN frame before bit stuffing (stuffing adds up to ~20 %)."""
    return 47 + 8 * dlc


def bus_load_pct(frames_per_second, dlc=8, bitrate=C.BITRATE):
    """Estimated bus load in percent. 1500 fps of 8-byte frames is about 33 %."""
    return 100.0 * frames_per_second * frame_bits(dlc) / bitrate
