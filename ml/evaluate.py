"""Honest evaluation of ml/models/model.json (roadmap step 2.5).

    python -m ml.evaluate --split val      # while you are still tuning
    python -m ml.evaluate --split test     # ONCE, at the very end
    python -m ml.evaluate --split test --write docs/phase2_results.md

Everything here comes from SIMULATION and must be called that in any report.
"""
import argparse
import platform
from pathlib import Path

import numpy as np

from core.model import SvmModel, MODEL_PATH
from ml import dataset as D
from ml import evaluation as E


def build_report(model, data, split, model_path):
    healthy_seeds = D.VAL_SEEDS if split == "val" else D.TEST_SEEDS
    fault_seeds = D.FAULT_VAL_SEEDS if split == "val" else D.FAULT_TEST_SEEDS
    h = E.healthy_report(model, data, healthy_seeds)
    f = E.fault_report(model, data, fault_seeds)
    size_kb = Path(model_path).stat().st_size / 1024
    L = []
    L.append(f"# Phase 2 results note ({split} runs, SIMULATION only)\n")
    L.append("These numbers come from the Python simulator. They will be re-measured on "
             "real hardware in Phases 5 and 8. All thresholds are starting values.\n")
    L.append(f"- Model version: {model.version}, nu = {model.params.get('nu')}, gamma = {model.gamma}")
    L.append(f"- Support vectors: {model.n_sv}, model.json size: {size_kb:.1f} KB")
    L.append(f"- Python {platform.python_version()}, numpy {np.__version__}\n")
    L.append("## False positives on healthy runs\n")
    L.append("| Healthy windows | Hours | Flagged windows | Flagged % | Episodes (3+ in a row) | Episodes per hour |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    L.append(f"| {h['windows']} | {h['hours']:.2f} | {h['flagged_windows']} | "
             f"{100 * h['flagged_fraction']:.2f} | {h['episodes']} | {h['episodes_per_hour']:.1f} |\n")
    L.append("## Detection by the SVM alone\n")
    L.append("| Injected condition | Runs | Detected | Mean latency (s) | Max latency (s) | Expected |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for k, r in f.items():
        ml_ = "-" if r["mean_latency_s"] is None else f"{r['mean_latency_s']:.2f}"
        mx = "-" if r["max_latency_s"] is None else f"{r['max_latency_s']:.2f}"
        L.append(f"| {k} | {r['runs']} | {r['detected']} | {ml_} | {mx} | {E.EXPECTED[k]} |")
    L.append("\nLatency = time from the injection until the SVM has flagged 3 windows in a row (the policy rule; one stray flag does not count). "
             "Detection is hybrid: the rule-based monitors (heartbeat, rate, drift) cover what "
             "the SVM cannot see, and the context rules decide what to do.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--split", choices=["val", "test"], default="val")
    ap.add_argument("--model", default=str(MODEL_PATH))
    ap.add_argument("--write", default=None, help="also save the note to this markdown file")
    args = ap.parse_args()
    model = SvmModel.load(args.model)
    text = build_report(model, D.load(), args.split, args.model)
    print(text)
    if args.write:
        Path(args.write).parent.mkdir(parents=True, exist_ok=True)
        Path(args.write).write_text(text, encoding="utf-8")
        print(f"saved {args.write}")


if __name__ == "__main__":
    main()
