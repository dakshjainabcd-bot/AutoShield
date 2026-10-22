# Phase 2 results note (test runs, SIMULATION only)

These numbers come from the Python simulator. They will be re-measured on real hardware in Phases 5 and 8. All thresholds are starting values.

- Model version: 1.0, nu = 0.01, gamma = 0.05
- Support vectors: 44, model.json size: 6.6 KB
- Python 3.11.9, numpy 2.4.6

## False positives on healthy runs

| Healthy windows | Hours | Flagged windows | Flagged % | Episodes (3+ in a row) | Episodes per hour |
| --- | --- | --- | --- | --- | --- |
| 23964 | 0.67 | 239 | 1.00 | 6 | 9.0 |

## Detection by the SVM alone

| Injected condition | Runs | Detected | Mean latency (s) | Max latency (s) | Expected |
| --- | --- | --- | --- | --- | --- |
| flood | 4 | 4 | 0.30 | 0.30 | SVM should detect |
| hang | 4 | 4 | 0.30 | 0.30 | SVM should detect (heartbeat monitor also does) |
| drift | 4 | 0 | - | - | NOT visible in the 6 features; the drift monitor handles it |
| faulty_fw | 4 | 4 | 0.30 | 0.30 | SVM should detect |
| test_burst | 4 | 4 | 0.30 | 0.30 | SVM flags it; the CONTEXT rule keeps severity Normal |

Latency = time from the injection until the SVM has flagged 3 windows in a row (the policy rule; one stray flag does not count). Detection is hybrid: the rule-based monitors (heartbeat, rate, drift) cover what the SVM cannot see, and the context rules decide what to do.
