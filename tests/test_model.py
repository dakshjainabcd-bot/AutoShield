"""Phase 2: the hand-written SVM formula must equal scikit-learn (roadmap step 2.4)."""
import json

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from core.features import FEATURE_NAMES
from core.model import SvmModel, MODEL_PATH
from ml import train as T


def synthetic_data(n=600, seed=0):
    rng = np.random.default_rng(seed)
    base = np.array([71.0, 0.70, 100.0, 0.7, 20.0, 0.4])
    return base + rng.normal(0, 1, (n, 6)) * np.array([0.5, 0.01, 0.3, 0.1, 0.1, 0.05])


def test_manual_formula_matches_scikit_learn_on_200_plus_windows(tmp_path):
    X = synthetic_data()
    scaler, svm = T.fit(X, nu=0.05, gamma=0.1)
    path = tmp_path / "model.json"
    diff = T.export_model(scaler, svm, 0.05, 0.1, path, "t1", X, [0], 1)   # raises if not equal
    assert diff < 1e-9
    model = SvmModel.load(path)
    test = synthetic_data(300, seed=1)
    ref = svm.decision_function(scaler.transform(test))
    assert np.max(np.abs(model.decision_many(test) - ref)) < 1e-9
    one = [model.decision(test[i]) for i in range(250)]
    assert np.max(np.abs(np.array(one) - ref[:250])) < 1e-9
    assert model.n_sv == svm.support_vectors_.shape[0]


def test_score_convention_is_minus_decision_and_threshold_rule(tmp_path):
    X = synthetic_data()
    scaler, svm = T.fit(X, 0.05, 0.1)
    T.export_model(scaler, svm, 0.05, 0.1, tmp_path / "m.json", "t", X, [0], 1)
    m = SvmModel.load(tmp_path / "m.json")
    x = X[0]
    assert m.anomaly_score(x) == pytest.approx(-m.decision(x))
    far = np.array([5000.0, 1.0, 1000.0, 0.0, 1000.0, 0.0])             # a flood-like vector
    assert m.is_anomaly(far) and m.anomaly_score(far) > 0
    assert not m.is_anomaly(np.median(X, axis=0))


def test_exported_json_has_every_field_the_firmware_needs(tmp_path):
    X = synthetic_data()
    scaler, svm = T.fit(X, 0.05, 0.1)
    T.export_model(scaler, svm, 0.05, 0.1, tmp_path / "m.json", "7.7", X, [3, 4], 20)
    p = json.loads((tmp_path / "m.json").read_text())
    for key in ("version", "feature_names", "scaler_mean", "scaler_scale", "gamma", "intercept",
                "dual_coef", "support_vectors", "threshold", "trained_utc"):
        assert key in p
    assert p["feature_names"] == FEATURE_NAMES and p["version"] == "7.7"
    assert len(p["scaler_mean"]) == len(p["scaler_scale"]) == 6
    assert len(p["dual_coef"]) == len(p["support_vectors"]) == p["n_support"]


def test_model_rejects_wrong_feature_order_and_bad_shapes(tmp_path):
    X = synthetic_data()
    scaler, svm = T.fit(X, 0.05, 0.1)
    T.export_model(scaler, svm, 0.05, 0.1, tmp_path / "m.json", "t", X, [0], 1)
    p = json.loads((tmp_path / "m.json").read_text())
    bad = dict(p, feature_names=list(reversed(FEATURE_NAMES)))
    with pytest.raises(ValueError):
        SvmModel(bad)
    bad = dict(p, dual_coef=p["dual_coef"][:-1])
    with pytest.raises(ValueError):
        SvmModel(bad)


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="run python -m ml.train first")
def test_trained_model_calls_healthy_normal_and_flood_anomalous():
    m = SvmModel.load()
    healthy = np.array([71.0, 0.70, 100.0, 0.7, 20.0, 0.4])
    flood = np.array([1500.0, 0.95, 100.0, 0.7, 20.0, 0.4])
    hang = np.array([61.0, 0.80, 1000.0, 0.0, 20.0, 0.4])
    assert m.anomaly_score(healthy) < 0 < m.anomaly_score(flood)
    assert m.anomaly_score(hang) > 0
