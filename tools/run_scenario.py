"""Run a scripted scenario and print the event timeline (roadmap step 1.9).

Run from the repository root:
    python tools/run_scenario.py
    python tools/run_scenario.py --seed 7 --duration 120
    python tools/run_scenario.py --no-auto-recovery      # detect and report only
    python tools/run_scenario.py --svm                   # Phase 2: plug in ml/models/model.json
"""
import argparse
import sys
from pathlib import Path

# Make 'core' and 'sim' importable when this file is run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.model import SvmModel, MODEL_PATH  # noqa: E402
from sim.runner import run_closed_loop            # noqa: E402
from sim.scenarios import DEFAULT_SCENARIO, DEFAULT_DURATION  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--seed", type=int, default=1, help="random seed (same seed = same run)")
    ap.add_argument("--duration", type=float, default=DEFAULT_DURATION, help="seconds to simulate")
    ap.add_argument("--no-auto-recovery", action="store_true", help="detect and report, never act")
    ap.add_argument("--svm", action="store_true", help="use the trained SVM (needs ml/models/model.json)")
    args = ap.parse_args()

    detector = None
    if args.svm:
        if not MODEL_PATH.exists():
            sys.exit(f"No model file at {MODEL_PATH}. Run:  python -m ml.train")
        detector = SvmModel.load()

    res = run_closed_loop(DEFAULT_SCENARIO, args.duration, seed=args.seed,
                          auto_recovery=not args.no_auto_recovery, detector=detector)

    rows = [(t, "BENCH", "", text) for t, text in res.scenario_log]
    rows += [(e["t_ms"] / 1000.0, e["kind"], e["severity"], e["detail"]) for e in res.events]
    rows.sort(key=lambda r: r[0])

    print(f"AutoShield scenario run: seed={args.seed}, duration={args.duration:.0f} s, "
          f"auto_recovery={not args.no_auto_recovery}, svm={'on' if detector else 'off'}")
    print(f"{'time (s)':>9}  {'event':<16} {'severity':<9} detail")
    print("-" * 72)
    for t, kind, sev, detail in rows:
        print(f"{t:9.1f}  {kind:<16} {sev:<9} {detail}")
    print("-" * 72)
    print(f"{len(res.events)} supervisor events, {len(res.steps)} windows evaluated")


if __name__ == "__main__":
    main()
