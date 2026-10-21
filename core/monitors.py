"""The three rule-based monitors (roadmap step 1.7).

They are deterministic and explainable. The SVM (Phase 2) is the general
behavioural detector; these catch specific faults. Detection is hybrid.
"""
from collections import Counter

from core import catalogue as C


class HeartbeatMonitor:
    """Flags the node as 'missed' when the last 0x100 frame is older than the deadline."""

    def __init__(self, deadline_ms=300.0, t_start=0.0):
        self.deadline_ms = deadline_ms
        self.t_start = t_start
        self.last_hb = None

    def observe(self, frame):
        if frame[1] == C.ID_NODE_HB:
            t = frame[0]
            if self.last_hb is None or t > self.last_hb:
                self.last_hb = t

    def age_ms(self, t_now):
        """Time since the last heartbeat. Before the first one: time since start."""
        ref = self.t_start if self.last_hb is None else self.last_hb
        return max(0.0, (t_now - ref) * 1000.0)

    def missed(self, t_now):
        # 'greater than': exactly 300 ms is still fine. The tiny margin absorbs
        # floating-point noise ((1.3 - 1.0) * 1000 is 300.00000000000006).
        return self.age_ms(t_now) > self.deadline_ms + 1e-6


class RateMonitor:
    """Per-ID rate monitor (flooding).

    limit for an ID = rate_factor x expected rate, if the ID has an expected
    rate; otherwise rate_unknown_limit_hz (this covers IDs outside the
    catalogue AND catalogue IDs with no fixed rate: 0x010, 0x050, 0x1F0).
    An ID must exceed its limit in `consecutive` windows in a row.
    0x1F0 is ignored while a gateway-started test burst is active.
    """

    def __init__(self, rate_factor=3.0, unknown_limit_hz=20.0, consecutive=3):
        self.rate_factor = rate_factor
        self.unknown_limit_hz = unknown_limit_hz
        self.consecutive = consecutive
        self._streak = {}
        self.offenders = set()

    def limit_hz(self, can_id):
        exp = C.EXPECTED_RATE_HZ.get(can_id)
        return self.rate_factor * exp if exp is not None else self.unknown_limit_hz

    def update(self, window, W=1.0, test_burst_active=False):
        """Feed one window. Returns True if a flood is flagged."""
        counts = Counter(f[1] for f in window)
        over = set()
        for can_id, n in counts.items():
            if test_burst_active and can_id == C.ID_TEST_BURST:
                continue
            if n / W > self.limit_hz(can_id):
                over.add(can_id)
        for can_id in list(self._streak):
            if can_id not in over:
                del self._streak[can_id]
        for can_id in over:
            self._streak[can_id] = self._streak.get(can_id, 0) + 1
        self.offenders = {i for i, s in self._streak.items() if s >= self.consecutive}
        return bool(self.offenders)


class DriftMonitor:
    """Sensor drift: EWMA of (node gyro_z - reference gyro_z), in centi-deg/s.

    State is 'ok', 'warn' or 'fault'. The residual magnitude must stay above a
    limit for `consecutive` windows in a row. update(None) keeps the last state
    (no IMU frames or no reference sample in this window).
    """

    def __init__(self, alpha=0.1, warn=10.0, fault=20.0, consecutive=5):
        self.alpha = alpha
        self.warn = warn
        self.fault = fault
        self.consecutive = consecutive
        self.ewma = 0.0
        self.state = "ok"
        self._n_warn = 0
        self._n_fault = 0

    def update(self, residual):
        if residual is None:
            return self.state
        self.ewma = (1 - self.alpha) * self.ewma + self.alpha * residual
        mag = abs(self.ewma)
        self._n_warn = self._n_warn + 1 if mag > self.warn else 0
        self._n_fault = self._n_fault + 1 if mag > self.fault else 0
        if self._n_fault >= self.consecutive:
            self.state = "fault"
        elif self._n_warn >= self.consecutive:
            self.state = "warn"
        else:
            self.state = "ok"
        return self.state

    def trust(self):
        """clamp(1 - |ewma| / fault limit, 0, 1). Defined in roadmap step 8.4."""
        return max(0.0, min(1.0, 1.0 - abs(self.ewma) / self.fault))
