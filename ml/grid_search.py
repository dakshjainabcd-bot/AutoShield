"""Choose nu and gamma on the VALIDATION runs (roadmap step 2.3).

    python -m ml.grid_search

The TEST runs are never touched here. Pick a row that
  1. detects flood, hang and faulty_fw in every validation run,
  2. has few false-positive episodes per hour,
  3. has few support vectors (the ESP32 must evaluate all of them every 100 ms).
"""
import argparse
import itertools

import numpy as np

from core.model import SvmModel
from ml import dataset as D
from ml import evaluation as E
from ml import train as T

NUS = [0.005, 0.01, 0.02, 0.05]
GAMMAS = [0.05, 0.1, 1.0 / 6, 0.5]
MUST_DETECT = ("flood", "hang", "faulty_fw")


def model_from(scaler, svm, gamma):
    """In-memory SvmModel (same maths as model.json) without writing a file."""
    return SvmModel({
        "version": "grid", "feature_names": T.FEATURE_NAMES,
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "gamma": gamma, "intercept": float(svm.intercept_[0]),
        "dual_coef": svm.dual_coef_[0].tolist(),
        "support_vectors": svm.support_vectors_.tolist(), "threshold": 0.0})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--stride", type=int, default=T.DEFAULT_STRIDE)
    args = ap.parse_args()

    data = D.load()
    X = D.healthy_matrix(data, D.TRAIN_SEEDS, stride=args.stride)
    print(f"training windows: {len(X)} (stride {args.stride})\n")
    print(f"{'nu':>6} {'gamma':>7} {'SVs':>5} {'flagged %':>10} {'FP ep/h':>8} "
          f"{'flood':>6} {'hang':>6} {'fw':>6} {'latency s (flood/hang/fw)':>27}")
    for nu, gamma in itertools.product(NUS, GAMMAS):
        scaler, svm = T.fit(X, nu, gamma)
        m = model_from(scaler, svm, gamma)
        h = E.healthy_report(m, data, D.VAL_SEEDS)
        f = E.fault_report(m, data, D.FAULT_VAL_SEEDS)
        lat = "/".join("-" if f[k]["mean_latency_s"] is None else f"{f[k]['mean_latency_s']:.2f}"
                       for k in MUST_DETECT)
        print(f"{nu:6.3f} {gamma:7.4f} {m.n_sv:5d} {100 * h['flagged_fraction']:10.2f} "
              f"{h['episodes_per_hour']:8.1f} "
              f"{f['flood']['detected']}/{f['flood']['runs']:>3} "
              f"{f['hang']['detected']}/{f['hang']['runs']:>3} "
              f"{f['faulty_fw']['detected']}/{f['faulty_fw']['runs']:>3} {lat:>27}")


if __name__ == "__main__":
    main()
