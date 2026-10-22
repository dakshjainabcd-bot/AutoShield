"""The reference supervisor: features + monitors (+ optional SVM) + policy in one loop.

Phase 2 wraps this in the 'virtual gateway' (backend/gateway.py). The firmware in
Phase 5 must give the same answers on the same trace (replay parity test).

Call step(t_end, new_frames, new_ref_samples) once every 100 ms. It only looks
at frames and reference samples, never at simulator internals.

Phase 2 change: an optional `detector` (core/model.py: SvmModel) can be plugged
in. It needs two things: anomaly_score(features) and a threshold attribute.
With detector=None the behaviour is exactly the Phase 1 behaviour.
"""
from dataclasses import dataclass
from typing import List, Optional

from core import catalogue as C
from core import can_codec as codec
from core.config import load_config
from core.features import select_window, features_from_window, bus_load_pct
from core.monitors import HeartbeatMonitor, RateMonitor, DriftMonitor
from core.policy import PolicyEngine, Flags, Context, Decision, make_event


@dataclass
class StepResult:
    t: float
    features: List[float]
    fps: float
    load_pct: float
    hb_age_ms: float
    flags: Flags
    context: Context
    drift_ewma: float
    drift_trust: float
    decision: Decision
    evaluated: bool            # False during the first window (warm-up)
    anomaly_score: float = 0.0   # SVM score (0.0 when no detector); higher = more unusual
    anomaly_raw: bool = False    # score above threshold, BEFORE the context rules below


class Supervisor:
    def __init__(self, cfg=None, run_id=0, auto_recovery=True, detector=None):
        self.cfg = cfg or load_config()
        m = self.cfg["monitors"]
        self.W = self.cfg["window_s"]
        self.step_s = self.cfg["step_s"]
        self.hb = HeartbeatMonitor(m["hb_deadline_ms"])
        self.rate = RateMonitor(m["rate_factor"], m["rate_unknown_limit_hz"],
                                m["rate_consecutive_windows"])
        self.drift = DriftMonitor(m["drift_ewma_alpha"], m["drift_warn_cdps"],
                                  m["drift_fault_cdps"], m["drift_consecutive_windows"])
        self.policy = PolicyEngine(self.cfg, run_id=run_id, auto_recovery=auto_recovery)
        self.detector = detector
        self._held = []        # frames not yet "arrived" (t >= t_end)
        self._buf = []         # frames inside the rolling buffer
        self._ref = []         # reference gyro samples (t, gz)
        self._burst_until = -1.0
        self._burst_end = None
        self._grace_until = -1.0
        self._queued = []      # events created between steps
        self.run_id = run_id
        self.isolated = False
        self.node_state = "UNKNOWN"

    # ----- context the gateway itself controls ----------------------------
    def start_test_burst(self, t, duration_s):
        """The gateway commanded a test burst. Burst frames stay inside the 1 s
        window for W seconds after the burst ends, so the context stays active
        for duration + W (otherwise the monitor would fire right after the burst)."""
        self._burst_until = max(self._burst_until, t + duration_s + self.W)
        self._burst_end = t + duration_s
        self._queued.append(make_event(t, "test_burst_started", "NORMAL",
                                       f"{duration_s:g} s", self.run_id))

    def start_deploy(self, t, grace_s=2.0):
        """A firmware deployment started. The node reboots and is silent for a
        moment, so 'heartbeat missed' AND the SVM anomaly are ignored for grace_s
        (boot settling, roadmap 7.5). Without this the supervisor would try to
        restart (or roll back) a node that is simply booting its new image."""
        self._grace_until = t + grace_s
        self._queued.append(make_event(t, "fw_deploy_started", "NORMAL", "canary", self.run_id))

    def test_burst_active(self, t):
        return t < self._burst_until

    # ----- main step -------------------------------------------------------
    def step(self, t_end, new_frames=(), new_ref=()):
        self._held.extend(new_frames)
        ready = sorted((f for f in self._held if f[0] < t_end), key=lambda f: f[0])
        self._held = [f for f in self._held if f[0] >= t_end]
        for f in ready:
            self._buf.append(f)
            self.hb.observe(f)
            if f[1] == C.ID_NODE_HB:
                code = codec.decode_hb(f.data)["state_code"] if f.data else 1
                self.node_state = C.NODE_STATE_NAMES.get(code, "UNKNOWN")
        self._ref.extend(new_ref)
        lo = t_end - self.W
        self._buf = [f for f in self._buf if f[0] >= lo - 0.2]
        self._ref = [r for r in self._ref if r[0] >= t_end - 2 * self.step_s]

        window = select_window(self._buf, t_end, self.W)
        feats = features_from_window(window, self.W)
        fps = len(window) / self.W
        age = self.hb.age_ms(t_end)

        evaluated = t_end >= self.W - 1e-9
        burst = self.test_burst_active(t_end)
        score, anomaly_raw, anomaly = 0.0, False, False
        if evaluated:
            flood = self.rate.update(window, self.W, test_burst_active=burst)
            hb_missed = self.hb.missed(t_end) and t_end >= self._grace_until
            self.drift.update(self._residual(window, t_end))
            if self.detector is not None:
                score = float(self.detector.anomaly_score(feats))
                anomaly_raw = score > self.detector.threshold
                # Context rules: an isolated node and a node that is still booting a
                # new image are silent on purpose, so their odd features are not a fault.
                anomaly = anomaly_raw and (t_end >= self._grace_until) and not self.isolated
        else:
            flood, hb_missed = False, False
        flags = Flags(anomaly=anomaly, hb_missed=hb_missed, flood=flood, drift=self.drift.state)
        ctx = Context(test_burst=burst, node_state=self.node_state, isolated=self.isolated)
        if evaluated:
            dec = self.policy.step(t_end, flags, ctx)
        else:
            dec = Decision()
        if self._burst_end is not None and t_end >= self._burst_end - 1e-9:
            self._queued.append(make_event(self._burst_end, "test_burst_ended", "NORMAL",
                                           "", self.run_id))
            self._burst_end = None
        dec.events = self._queued + dec.events
        self._queued = []
        if dec.action == "ISOLATE":
            self.isolated = True
        elif dec.action == "RESTORE":
            self.isolated = False
        return StepResult(t_end, feats, fps, bus_load_pct(fps), age, flags, ctx,
                          self.drift.ewma, self.drift.trust(), dec, evaluated,
                          anomaly_score=score, anomaly_raw=anomaly_raw)

    def _residual(self, window, t_end):
        """Mean node gyro_z minus mean reference gyro_z over the last 100 ms."""
        lo = t_end - self.step_s
        node = [codec.decode_imu(f.data)["gz_cdps"] for f in window
                if f[1] == C.ID_NODE_IMU and f[0] >= lo and f.data]
        ref = [r[1] for r in self._ref if lo <= r[0] < t_end]
        if not node or not ref:
            return None
        return sum(node) / len(node) - sum(ref) / len(ref)
