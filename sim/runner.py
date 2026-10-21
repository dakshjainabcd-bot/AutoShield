"""Closed-loop scenario runner: simulator + reference supervisor.

Every 100 ms: advance the simulator, give the new frames to the supervisor, and
carry out whatever action the supervisor decided. The supervisor never looks
inside the simulator; it only sees frames.
"""
from dataclasses import dataclass, field
from typing import List

from core.config import load_config
from core.supervisor import Supervisor, StepResult
from sim.scenarios import ground_truth
from sim.vehicle_sim import VehicleSim

# Supervisor action -> simulator command (informational actions do nothing to the bus)
_EXECUTE = {"SOFT_RESET": "SOFT_RESET", "HARD_RESET": "HARD_RESET", "ISOLATE": "ISOLATE",
            "RESTORE": "RESTORE", "FW_ROLLBACK": "FW_ROLLBACK", "SAFE_MODE": "SAFE_MODE",
            "FW_COMMIT": "FW_COMMIT"}


@dataclass
class RunResult:
    steps: List[StepResult] = field(default_factory=list)
    events: List[dict] = field(default_factory=list)    # supervisor events
    scenario_log: List[tuple] = field(default_factory=list)  # (t, text) what the bench did
    ground_truth: List[tuple] = field(default_factory=list)
    sim: VehicleSim = None


def run_closed_loop(scenario, duration, seed=1, auto_recovery=True, cfg=None, run_id=0):
    cfg = cfg or load_config()
    step_s = cfg["step_s"]
    sim = VehicleSim(seed=seed)
    sup = Supervisor(cfg, run_id=run_id, auto_recovery=auto_recovery)
    res = RunResult(ground_truth=ground_truth(scenario), sim=sim)
    pending = sorted(scenario, key=lambda e: e[0])
    n_steps = int(round(duration / step_s))
    for k in range(1, n_steps + 1):
        t_prev, t_end = round((k - 1) * step_s, 6), round(k * step_s, 6)
        while pending and pending[0][0] <= t_prev + 1e-9:
            _, kind, params = pending.pop(0)
            if kind == "test_burst":
                sup.start_test_burst(t_prev, params["duration_s"])
                sim.command("TEST_BURST", ms=int(params["duration_s"] * 1000))
            else:
                if kind == "faulty_fw":
                    sup.start_deploy(t_prev)
                sim.inject(kind, **params)
            res.scenario_log.append((t_prev, f"bench: {kind} {params}"))
        frames, ref = sim.advance(t_end)
        r = sup.step(t_end, frames, ref)
        res.steps.append(r)
        res.events.extend(r.decision.events)
        cmd = _EXECUTE.get(r.decision.action)
        if cmd:
            sim.command(cmd)
    return res
