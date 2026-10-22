"""Generate the feature windows for training and evaluation (roadmap step 2.1).

Every window comes from the SAME code path the live system uses
(sim.runner.run_closed_loop -> Supervisor -> core.features), so training features
and run-time features can never disagree.

Splits are by WHOLE RUNS, never by window: neighbouring windows overlap by 90 %,
so mixing them across sets would leak information (data leakage).
"""
from pathlib import Path

import numpy as np

from sim.params import SIM_DEFAULTS
from sim.runner import run_closed_loop

RAW_DIR = Path(__file__).resolve().parent / "data" / "raw"
CACHE = RAW_DIR / "features.npz"

TRAIN_SEEDS = list(range(1000, 1012))     # 12 healthy runs: fit the model
VAL_SEEDS = list(range(1012, 1016))       # 4 healthy runs: choose nu and gamma
TEST_SEEDS = list(range(1016, 1020))      # 4 healthy runs: final report, used ONCE
FAULT_VAL_SEEDS = list(range(2000, 2004))
FAULT_TEST_SEEDS = list(range(3000, 3004))

HEALTHY_SECONDS = 600.0
FAULT_SECONDS = 40.0
FAULT_START = 20.0

# name -> (scenario kind, parameters). Run with auto_recovery=False so the
# supervisor only OBSERVES and the fault is never fixed during the run.
FAULTS = {
    "flood": ("flood", {"duration_s": 5.0}),
    "hang": ("hang", {}),
    "drift": ("drift", {"slope": 50.0}),
    "faulty_fw": ("faulty_fw", {}),
    "test_burst": ("test_burst", {"duration_s": 2.0}),
}

_NOISY = ("hb_jitter_s", "imu_jitter_s", "gw_jitter_s", "fwinfo_jitter_s", "imu_noise_cdps")


def sim_params_for(seed):
    """Slightly different timing noise for every run (0.8x to 1.5x of the defaults)."""
    f = float(np.random.default_rng(10_000 + seed).uniform(0.8, 1.5))
    return {k: SIM_DEFAULTS[k] * f for k in _NOISY}


def _evaluated(res):
    steps = [s for s in res.steps if s.evaluated]
    t = np.array([s.t for s in steps])
    X = np.array([s.features for s in steps])
    return t, X


def healthy_run(seed, seconds=HEALTHY_SECONDS):
    res = run_closed_loop([], seconds, seed=seed, sim_params=sim_params_for(seed))
    return _evaluated(res)


def fault_run(fault, seed, seconds=FAULT_SECONDS, t_fault=FAULT_START):
    kind, params = FAULTS[fault]
    res = run_closed_loop([(t_fault, kind, dict(params))], seconds, seed=seed,
                          auto_recovery=False, sim_params=sim_params_for(seed))
    return _evaluated(res)


def build(force=False, verbose=True):
    """Create ml/data/raw/features.npz (about 1 minute). Re-uses it if it exists."""
    if CACHE.exists() and not force:
        return CACHE
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for seed in TRAIN_SEEDS + VAL_SEEDS + TEST_SEEDS:
        t, X = healthy_run(seed)
        arrays[f"healthy_{seed}"] = X
        if verbose:
            print(f"healthy run seed {seed}: {len(X)} windows")
    for fault in FAULTS:
        for seed in FAULT_VAL_SEEDS + FAULT_TEST_SEEDS:
            t, X = fault_run(fault, seed)
            arrays[f"fault_{fault}_{seed}_X"] = X
            arrays[f"fault_{fault}_{seed}_t"] = t
        if verbose:
            print(f"fault runs done: {fault}")
    np.savez_compressed(CACHE, **arrays)
    if verbose:
        print(f"saved {CACHE}")
    return CACHE


def load():
    """Return a dict of numpy arrays from the cache (builds it first if missing)."""
    build(force=False)
    with np.load(CACHE) as z:
        return {k: z[k] for k in z.files}


def healthy_matrix(data, seeds, stride=1):
    """Stack the healthy windows of the given runs. stride=20 keeps every 20th window
    (every 2 s), which removes the heavy overlap and keeps training fast."""
    return np.vstack([data[f"healthy_{s}"][::stride] for s in seeds])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate ml/data/raw/features.npz")
    ap.add_argument("--force", action="store_true", help="regenerate even if the file exists")
    build(force=ap.parse_args().force)
