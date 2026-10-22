"""Save a simulated run to web/assets/sample_run.jsonl (roadmap step 3.5, prepared in Phase 2).

R4 uses this file for the dashboard's 'replay' mode, so the UI can be built and
shown without the backend. One JSON object per line: telemetry and event messages,
in time order. Run from the repository root:

    python tools/make_sample_run.py
    python tools/make_sample_run.py --out web/assets/sample_run.jsonl --seed 1
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.gateway import VirtualGateway          # noqa: E402
from core.model import SvmModel, MODEL_PATH         # noqa: E402
from sim.scenarios import DEFAULT_SCENARIO, DEFAULT_DURATION  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out", default="web/assets/sample_run.jsonl")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duration", type=float, default=DEFAULT_DURATION)
    args = ap.parse_args()

    model = SvmModel.load() if MODEL_PATH.exists() else None
    if model is None:
        print("note: no model file, the sample will have no SVM scores (run python -m ml.train first)")
    gw = VirtualGateway(seed=args.seed, model=model, run_id=1)
    pending = sorted(DEFAULT_SCENARIO, key=lambda e: e[0])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_tel = n_ev = 0
    with open(out, "w", encoding="utf-8") as fh:
        for _ in range(int(round(args.duration / gw.step_s))):
            while pending and pending[0][0] <= gw.sim_time + 1e-9:
                _, kind, params = pending.pop(0)
                gw.apply(kind, **params)
            tel, events = gw.step()
            fh.write(json.dumps(tel) + "\n")
            n_tel += 1
            for ev in events:
                fh.write(json.dumps(ev) + "\n")
                n_ev += 1
    print(f"wrote {out}: {n_tel} telemetry lines, {n_ev} events, {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
