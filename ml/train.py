"""Train the One-Class SVM and export model.json (roadmap steps 2.2 and 2.4).

    python -m ml.train                       # nu=0.01, gamma=0.05, stride 20
    python -m ml.train --nu 0.02 --gamma 0.1

Trains ONLY on healthy windows from the TRAIN runs. Then it proves that the
hand-written formula in core/model.py gives the same numbers as scikit-learn.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from core.features import FEATURE_NAMES
from core.model import SvmModel, MODEL_PATH
from ml import dataset as D

# Chosen from ml/grid_search.py on the VALIDATION runs (see docs/phase2_roadmap.md).
DEFAULT_NU = 0.01
DEFAULT_GAMMA = 0.05
DEFAULT_STRIDE = 20


def fit(X, nu, gamma):
    """Scale, then fit. gamma is a NUMBER (not 'scale') so we know what to export."""
    scaler = StandardScaler().fit(X)
    svm = OneClassSVM(kernel="rbf", gamma=gamma, nu=nu).fit(scaler.transform(X))
    return scaler, svm


def export_model(scaler, svm, nu, gamma, path, version, X_train, train_seeds, stride,
                 threshold=0.0):
    """Write model.json, reload it with core.model.SvmModel and prove parity with
    scikit-learn on at least 200 windows. Returns the largest absolute difference."""
    params = {
        "format": 1,
        "version": version,
        "trained_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "feature_names": FEATURE_NAMES,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "gamma": float(gamma),
        "nu": float(nu),
        "intercept": float(svm.intercept_[0]),
        "dual_coef": svm.dual_coef_[0].tolist(),
        "support_vectors": svm.support_vectors_.tolist(),
        "n_support": int(svm.support_vectors_.shape[0]),
        "threshold": float(threshold),
        "training": {"n_windows": int(len(X_train)), "train_seeds": list(train_seeds),
                     "stride": int(stride), "sklearn_version": sklearn.__version__},
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(params, fh)
    model = SvmModel.load(path)
    n = max(200, min(len(X_train), 1000))
    X = np.asarray(X_train)[:n]
    ref = svm.decision_function(scaler.transform(X))
    mine = model.decision_many(X)
    diff = float(np.max(np.abs(ref - mine)))
    one = float(max(abs(model.decision(X[i]) - ref[i]) for i in range(200)))
    if diff > 1e-9 or one > 1e-9:
        raise RuntimeError(f"manual SVM does not match scikit-learn (diff {diff:.3g}, {one:.3g})")
    return diff


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--nu", type=float, default=DEFAULT_NU)
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    ap.add_argument("--stride", type=int, default=DEFAULT_STRIDE, help="keep every Nth window")
    ap.add_argument("--version", default="1.0", help="model version string (goes into telemetry)")
    ap.add_argument("--out", default=str(MODEL_PATH))
    args = ap.parse_args()

    gamma = args.gamma
    data = D.load()
    X = D.healthy_matrix(data, D.TRAIN_SEEDS, stride=args.stride)
    scaler, svm = fit(X, args.nu, gamma)
    diff = export_model(scaler, svm, args.nu, gamma, args.out, args.version, X,
                        D.TRAIN_SEEDS, args.stride)
    size_kb = Path(args.out).stat().st_size / 1024
    print(f"trained on {len(X)} healthy windows (nu={args.nu}, gamma={gamma:.6g})")
    print(f"support vectors: {svm.support_vectors_.shape[0]}   model.json: {size_kb:.1f} KB")
    print(f"manual formula vs scikit-learn, largest difference: {diff:.2e}  (must be tiny)")
    print(f"written: {args.out}")


if __name__ == "__main__":
    main()
