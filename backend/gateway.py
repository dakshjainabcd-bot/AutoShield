"""The VIRTUAL GATEWAY (roadmap step 2.7).

Simulator + reference supervisor (+ SVM) behind one object. Each call to step()
advances the simulated vehicle by 100 ms, lets the supervisor look at the new
frames, carries out the action it chose, and returns one telemetry message plus
the events of that window.

It is thread-safe: the backend runs step() in a worker thread while API requests
(inject, control) arrive from other threads, so every public method takes a lock.
"""
import threading

from backend.telemetry import NodeTracker, build_telemetry
from core.config import load_config
from core.supervisor import Supervisor
from sim.vehicle_sim import VehicleSim

# supervisor action -> simulator command (informational actions do nothing to the bus)
_EXECUTE = {"SOFT_RESET", "HARD_RESET", "ISOLATE", "RESTORE", "FW_ROLLBACK", "SAFE_MODE",
            "FW_COMMIT"}
KINDS = ("flood", "hang", "drift", "faulty_fw", "clear", "test_burst")


class BenchError(Exception):
    """The requested bench action cannot be done right now."""


class VirtualGateway:
    def __init__(self, seed=1, model=None, cfg=None, run_id=0, mode="sim", auto_recovery=True):
        self.cfg = cfg or load_config()
        self.seed = seed
        self.model = model
        self.mode = mode
        self.run_id = run_id
        self.step_s = self.cfg["step_s"]
        self._lock = threading.RLock()
        self._auto_recovery = auto_recovery
        self._build()

    # ----- setup -----------------------------------------------------------
    def _build(self):
        self.sim = VehicleSim(seed=self.seed)
        self.sup = Supervisor(self.cfg, run_id=self.run_id, auto_recovery=self._auto_recovery,
                              detector=self.model)
        self.tracker = NodeTracker()
        self.k = 0
        self.ref_gz = 0.0

    @property
    def model_version(self):
        return self.model.version if self.model is not None else "none"

    @property
    def threshold(self):
        return self.model.threshold if self.model is not None else 0.0

    @property
    def sim_time(self):
        return round(self.k * self.step_s, 6)

    def config_summary(self):
        return {"config": self.cfg, "model": self.model_version, "threshold": self.threshold,
                "seed": self.seed}

    def set_run_id(self, run_id):
        with self._lock:
            self.run_id = run_id
            self.sup.run_id = run_id
            self.sup.policy.run_id = run_id

    def set_auto_recovery(self, on):
        with self._lock:
            self._auto_recovery = bool(on)
            self.sup.policy.auto_recovery = bool(on)

    # ----- bench actions (what a test bench does) --------------------------------
    def apply(self, kind, **params):
        """kind: flood | hang | drift | faulty_fw | clear | test_burst.
        Same meaning as the scenario kinds in sim/scenarios.py (durations in seconds)."""
        if kind not in KINDS:
            raise ValueError(f"unknown bench action: {kind}")
        with self._lock:
            t = self.sim_time
            if kind == "test_burst":
                d = float(params.get("duration_s", 2.0))
                self.sup.start_test_burst(t, d)
                self.sim.command("TEST_BURST", ms=int(round(d * 1000)))
                return
            if kind == "faulty_fw":
                if self.sim.node.state in ("HUNG", "BOOT"):
                    raise BenchError("the node is hung or booting; reset the bench first")
                self.sup.start_deploy(t)
            self.sim.inject(kind, **params)

    def reset_bench(self):
        """Clear every fault and start a fresh simulation (time restarts at 0)."""
        with self._lock:
            self._build()

    # ----- one 100 ms step ---------------------------------------------------
    def step(self):
        """Returns (telemetry message, list of event messages)."""
        with self._lock:
            t_end = round((self.k + 1) * self.step_s, 6)
            frames, ref = self.sim.advance(t_end)
            res = self.sup.step(t_end, frames, ref)
            action = res.decision.action
            if action in _EXECUTE:
                self.sim.command(action)
            self.k += 1
            self.tracker.observe_frames(frames)
            if ref:
                self.ref_gz = ref[-1][1]
            tel = build_telemetry(
                res, mode=self.mode, run_id=self.run_id, model_version=self.model_version,
                threshold=self.threshold, tracker=self.tracker, ref_gz=self.ref_gz,
                auto_recovery=self._auto_recovery,
                hb_deadline_ms=self.cfg["monitors"]["hb_deadline_ms"])
            return tel, list(res.decision.events)
