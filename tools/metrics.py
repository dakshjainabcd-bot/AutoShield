"""Detection, response and recovery latency against ground truth (roadmap step 2.9).

    python tools/metrics.py                     # rules only, 5 seeds
    python tools/metrics.py --svm --seeds 10    # with the trained SVM
    python tools/metrics.py --svm --healthy-minutes 60

Definitions (all in SIMULATED seconds, from the gateway's own clock):
  detection  = first fault_detected (or sensor_flagged) event after the fault starts
               minus the time the fault started
  response   = first action_taken at or after detection, minus detection
  recovery   = first verify_ok after that action, minus the action
  false alarm = a fault_detected event outside every fault's attribution window
Reused in Phases 6 and 8 with real runs.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.model import SvmModel, MODEL_PATH                    # noqa: E402
from sim.runner import run_closed_loop                          # noqa: E402
from sim.scenarios import DEFAULT_SCENARIO, DEFAULT_DURATION, ground_truth  # noqa: E402

HORIZON_S = 20.0          # how long after a fault's start events still count as its own
DETECT_KINDS = ("fault_detected", "sensor_flagged")


def windows(gt):
    """[(fault, start, end)] attribution windows, half-open [start, end)."""
    out = []
    starts = [g[1] for g in gt]
    for i, (fault, start, _) in enumerate(gt):
        nxt = starts[i + 1] if i + 1 < len(starts) else float("inf")
        out.append((fault, start, min(start + HORIZON_S, nxt)))
    return out


def analyse(res):
    """Per-fault latencies for one run, plus its false alarms."""
    ev = [(e["t_ms"] / 1000.0, e) for e in res.events]
    per, attributed = {}, set()
    for fault, start, end in windows(res.ground_truth):
        inside = [(t, e) for t, e in ev if start <= t < end]
        attributed.update(id(e) for _, e in inside if e["kind"] == "fault_detected")
        det = next(((t, e) for t, e in inside if e["kind"] in DETECT_KINDS), None)
        r = {"detection": None, "response": None, "recovery": None}
        if det:
            r["detection"] = det[0] - start
            act = next(((t, e) for t, e in inside
                        if e["kind"] == "action_taken" and t >= det[0] - 1e-9), None)
            if act:
                r["response"] = act[0] - det[0]
                ok = next((t for t, e in inside if e["kind"] == "verify_ok" and t > act[0]), None)
                if ok is not None:
                    r["recovery"] = ok - act[0]
        per[fault] = r
    false_alarms = [e for _, e in ev if e["kind"] == "fault_detected" and id(e) not in attributed]
    return per, false_alarms


def stats(values):
    v = [x for x in values if x is not None]
    if not v:
        return "-"
    return f"{np.mean(v):.2f} (min {np.min(v):.2f}, max {np.max(v):.2f}, sd {np.std(v):.2f}) n={len(v)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5, help="number of scenario runs")
    ap.add_argument("--healthy-minutes", type=float, default=30.0)
    ap.add_argument("--svm", action="store_true")
    args = ap.parse_args()

    detector = None
    if args.svm:
        if not MODEL_PATH.exists():
            sys.exit(f"No model file at {MODEL_PATH}. Run:  python -m ml.train")
        detector = SvmModel.load()

    agg, false_total = {}, 0
    for s in range(args.seeds):
        res = run_closed_loop(DEFAULT_SCENARIO, DEFAULT_DURATION, seed=500 + s, detector=detector)
        per, fa = analyse(res)
        false_total += len(fa)
        for fault, r in per.items():
            for k, v in r.items():
                agg.setdefault(fault, {}).setdefault(k, []).append(v)
    n_h = max(1, int(round(args.healthy_minutes / 10.0)))
    h_alarms = 0
    for s in range(n_h):
        h = run_closed_loop([], 600.0, seed=900 + s, detector=detector)
        h_alarms += sum(1 for e in h.events if e["kind"] == "fault_detected")
    hours = n_h * 600.0 / 3600.0

    print(f"AutoShield metrics (SIMULATION), svm={'on' if detector else 'off'}, {args.seeds} scenario runs")
    print(f"{'fault':<10} {'detection s':<44} {'response s':<44} recovery s")
    for fault in ("flood", "hang", "drift", "faulty_fw"):
        a = agg[fault]
        missed = sum(1 for x in a["detection"] if x is None)
        print(f"{fault:<10} {stats(a['detection']):<44} {stats(a['response']):<44} {stats(a['recovery'])}"
              + (f"   MISSED {missed}" if missed else ""))
    print(f"\nfalse alarms inside the scenario runs: {false_total} (test burst included)")
    print(f"false alarms on {hours:.2f} h of healthy traffic: {h_alarms} "
          f"({h_alarms / hours:.2f} per hour)")
    print("drift has no recovery time on purpose: flagging a sensor is informational, not verified.")


if __name__ == "__main__":
    main()
