import numpy as np

from ml import dataset as D
from ml import evaluation as E


def test_sim_params_are_repeatable_and_vary_between_runs():
    assert D.sim_params_for(1000) == D.sim_params_for(1000)
    assert D.sim_params_for(1000) != D.sim_params_for(1001)
    base = 0.0005
    assert 0.8 * base <= D.sim_params_for(1000)["hb_jitter_s"] <= 1.5 * base


def test_splits_do_not_share_runs():
    sets = [set(D.TRAIN_SEEDS), set(D.VAL_SEEDS), set(D.TEST_SEEDS)]
    assert not (sets[0] & sets[1]) and not (sets[0] & sets[2]) and not (sets[1] & sets[2])
    assert not (set(D.FAULT_VAL_SEEDS) & set(D.FAULT_TEST_SEEDS))


def test_healthy_run_shape_and_values():
    t, X = D.healthy_run(1000, seconds=20.0)
    assert X.shape == (len(t), 6) and len(t) == 191            # windows end at 1.0, 1.1 ... 20.0 s
    assert abs(t[0] - 1.0) < 1e-9
    assert abs(X[:, 0].mean() - 71) < 2
    t2, X2 = D.healthy_run(1000, seconds=20.0)
    assert np.array_equal(X, X2)                               # same seed, same data


def test_fault_run_flood_has_huge_rate_after_injection():
    t, X = D.fault_run("flood", 2000)
    assert X[t < D.FAULT_START - 1.5, 0].max() < 100
    assert X[(t > D.FAULT_START + 1) & (t < D.FAULT_START + 4), 0].min() > 1000


def test_episodes_counts_runs_of_three_or_more():
    assert E.episodes([1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1]) == 2
    assert E.episodes([1, 1, 0, 1, 1, 0]) == 0
