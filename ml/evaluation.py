"""Shared evaluation helpers (roadmap steps 2.3 and 2.5)."""
import numpy as np

from ml import dataset as D

STEP_S = 0.1


def episodes(flags, min_len=3):
    """Number of runs of at least min_len consecutive True values.
    min_len=3 matches the policy: an anomaly needs 3 windows in a row to matter."""
    n, run = 0, 0
    for f in flags:
        run = run + 1 if f else 0
        if run == min_len:
            n += 1
    return n


def healthy_report(model, data, seeds):
    """False positives on healthy runs, scored with the given model."""
    n_win, n_flag, n_ep = 0, 0, 0
    for s in seeds:
        flags = model.anomaly_scores(data[f"healthy_{s}"]) > model.threshold
        n_win += len(flags)
        n_flag += int(flags.sum())
        n_ep += episodes(flags)
    hours = n_win * STEP_S / 3600.0
    return {"windows": n_win, "flagged_windows": n_flag,
            "flagged_fraction": n_flag / n_win,
            "episodes": n_ep, "hours": hours, "episodes_per_hour": n_ep / hours}


def fault_latencies(model, data, fault, seeds, min_len=3):
    """Per run: seconds from the injection until the SVM has flagged min_len windows in a
    row (the same rule the policy uses; a single stray flag is not a detection).
    None = never detected."""
    out = []
    for s in seeds:
        t = data[f"fault_{fault}_{s}_t"]
        X = data[f"fault_{fault}_{s}_X"]
        flagged = (model.anomaly_scores(X) > model.threshold) & (t > D.FAULT_START)
        run, hit = 0, None
        for i, f in enumerate(flagged):
            run = run + 1 if f else 0
            if run == min_len:
                hit = float(t[i] - D.FAULT_START)
                break
        out.append(hit)
    return out


def fault_report(model, data, seeds):
    rep = {}
    for fault in D.FAULTS:
        lat = fault_latencies(model, data, fault, seeds)
        got = [x for x in lat if x is not None]
        rep[fault] = {"runs": len(lat), "detected": len(got),
                      "mean_latency_s": float(np.mean(got)) if got else None,
                      "max_latency_s": float(np.max(got)) if got else None}
    return rep


# What the SVM is EXPECTED to do for each injected condition (the other detectors
# cover the rest: detection is hybrid).
EXPECTED = {
    "flood": "SVM should detect",
    "hang": "SVM should detect (heartbeat monitor also does)",
    "faulty_fw": "SVM should detect",
    "drift": "NOT visible in the 6 features; the drift monitor handles it",
    "test_burst": "SVM flags it; the CONTEXT rule keeps severity Normal",
}
