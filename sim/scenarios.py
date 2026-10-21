"""Scenario format and ground truth (roadmap step 1.9).

A scenario is a list of (time_s, kind, params) tuples. Kinds:
  flood      params: duration_s, rate_hz (optional)
  hang       params: boots (optional, number of reboots that hang again)
  drift      params: slope (centi-deg/s per second)
  faulty_fw  params: none  (deploys the faulty image as a canary)
  clear      params: none  (harness CLEAR: removes flood and drift)
  test_burst params: duration_s (the gateway commands a burst)
"""

# The scripted run from the roadmap: healthy 60 s, flood 60-70 s, hang at 90 s,
# drift from 120 s, faulty firmware at 150 s. Two extra events keep the faults
# independent: CLEAR at 140 s ends the drift, and a test burst at 170 s shows the
# context-aware behaviour (it must stay NORMAL).
DEFAULT_SCENARIO = [
    (60.0, "flood", {"duration_s": 10.0}),
    (90.0, "hang", {}),
    (120.0, "drift", {"slope": 50.0}),
    (140.0, "clear", {}),
    (150.0, "faulty_fw", {}),
    (170.0, "test_burst", {"duration_s": 2.0}),
]
DEFAULT_DURATION = 190.0

# Faults that count as ground truth (CLEAR and test_burst are not faults).
FAULT_KINDS = ("flood", "hang", "drift", "faulty_fw")


def ground_truth(scenario):
    """List of (fault, start, planned_end_or_None). Only floods have a planned end;
    for the others the end is whenever the recovery action completes."""
    out = []
    for t, kind, params in scenario:
        if kind in FAULT_KINDS:
            end = t + params["duration_s"] if kind == "flood" else None
            out.append((kind, t, end))
    return out
