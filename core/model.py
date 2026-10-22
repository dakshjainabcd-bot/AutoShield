"""The One-Class SVM, evaluated by hand (roadmap step 2.4).

scikit-learn is used only for TRAINING (ml/train.py). At run time, and later in the
ESP32 firmware, the decision function is computed with this plain formula:

    xs   = (x - mean) / scale                      scale the 6 features
    d2_k = sum_i (SV[k][i] - xs[i]) ** 2           squared distance to support vector k
    f(x) = sum_k dual[k] * exp(-gamma * d2_k) + intercept

Project convention (contracts/telemetry_schema.md):
    anomaly_score = -f(x)        higher = more unusual
    anomalous when anomaly_score > threshold      (threshold starts at 0)

This file needs only numpy, so scikit-learn is not needed to RUN the detector.
"""
import json
from pathlib import Path

import numpy as np

from core.features import FEATURE_NAMES

MODEL_PATH = Path(__file__).resolve().parent.parent / "ml" / "models" / "model.json"


class SvmModel:
    def __init__(self, params):
        if list(params["feature_names"]) != FEATURE_NAMES:
            raise ValueError("model.json feature order does not match core.features.FEATURE_NAMES")
        self.params = params
        self.version = str(params["version"])
        self.mean = np.asarray(params["scaler_mean"], dtype=float)
        self.scale = np.asarray(params["scaler_scale"], dtype=float)
        self.gamma = float(params["gamma"])
        self.sv = np.asarray(params["support_vectors"], dtype=float)      # (n_sv, 6)
        self.dual = np.asarray(params["dual_coef"], dtype=float)          # (n_sv,)
        self.intercept = float(params["intercept"])
        self.threshold = float(params.get("threshold", 0.0))
        n = len(FEATURE_NAMES)
        if self.sv.ndim != 2 or self.sv.shape[1] != n or self.dual.shape != (self.sv.shape[0],):
            raise ValueError("model.json arrays have inconsistent shapes")
        if self.mean.shape != (n,) or self.scale.shape != (n,):
            raise ValueError("model.json scaler arrays must have 6 numbers")

    @property
    def n_sv(self):
        return int(self.sv.shape[0])

    @classmethod
    def load(cls, path=None):
        with open(path or MODEL_PATH, "r", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def decision(self, x_raw):
        """f(x) for ONE feature vector (6 numbers). This is the formula the firmware ports."""
        xs = (np.asarray(x_raw, dtype=float) - self.mean) / self.scale
        d2 = ((self.sv - xs) ** 2).sum(axis=1)
        return float((self.dual * np.exp(-self.gamma * d2)).sum() + self.intercept)

    def decision_many(self, X_raw, chunk=2000):
        """f(x) for many rows. Same maths as decision(), done in chunks to save memory."""
        X = np.atleast_2d(np.asarray(X_raw, dtype=float))
        out = np.empty(len(X))
        for i in range(0, len(X), chunk):
            xs = (X[i:i + chunk] - self.mean) / self.scale
            d2 = ((xs[:, None, :] - self.sv[None, :, :]) ** 2).sum(axis=2)
            out[i:i + chunk] = (self.dual * np.exp(-self.gamma * d2)).sum(axis=1) + self.intercept
        return out

    def anomaly_score(self, x_raw):
        return -self.decision(x_raw)

    def anomaly_scores(self, X_raw):
        return -self.decision_many(X_raw)

    def is_anomaly(self, x_raw):
        return self.anomaly_score(x_raw) > self.threshold
