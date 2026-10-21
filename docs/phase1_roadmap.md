# AutoShield, Phase 1: Contracts and Simulation Core

A step-by-step guide for the person doing Phase 1. Beginner friendly: follow the steps in
order, run the check after every step, and do not move on until the check passes.

- **Goal:** a frozen set of interface contracts, and a software-only "virtual vehicle" that
  produces CAN-like traffic for healthy and faulty behaviour, with tested reference algorithms.
- **Lead:** R2 (simulator and algorithms) and R3 (contracts). R1 reviews the CAN catalogue. R4 starts wireframes.
- **Effort:** 7 to 10 days. **Depends on:** Phase 0. **Deferrable:** no.
- **Why it matters:** contracts let four people work at once without breaking each other. The simulator
  lets you build and test the whole system before touching hardware.

---

## 0. What was tested, and what was not

| Tested by running it (Linux, Python 3.12.3, numpy 2.5.4, pytest 9.1.1) | Not tested (do these on your machine) |
| --- | --- |
| All 81 tests pass in about 3 seconds. The full scripted scenario runs and prints the timeline shown in Step 9. The scenario was run with 40 different random seeds: every fault was detected and recovered every time, and 10 healthy runs of 5 minutes gave zero false alarms. | Windows and macOS commands, PowerShell activation, `git tag` and `git push` on your remote, the `Check on your machine` items below |

Every number in this guide (thresholds, noise levels, latencies) is a **starting value from simulation**,
not a measurement. Phase 4 and Phase 5 replace the guesses with real data.

---

## 1. Hands-on review of your repository and the roadmap

I went through every file you attached: the roadmap, the README, `requirements.txt`, `pytest.ini`,
`.gitignore`, `tools/check_env.py`, `tools/make_layout.py`, both Arduino test sketches, the `docs/` files,
`tests/test_smoke.py`, and all the placeholder files (`.gitkeep`, `__init__.py`).

### 1.1 What is already right

| Item | Verdict |
| --- | --- |
| Folder layout | Matches roadmap Section 8. `backend`, `core`, `ml`, `sim` each have an `__init__.py`, so `import core` works. |
| `pytest.ini` (`pythonpath = .`) | Correct. It is why `tests/` can import `core` and `sim`. Do not remove it. |
| `requirements.txt` | Phase 1 needs only `numpy` and `pytest`, both already listed. **No new packages for Phase 1.** |
| `.gitignore` | Fine for Phase 1. Phase 1 creates no large files. |
| `tools/check_env.py` | Works as is. |

### 1.2 Things to know about the repo

| # | Observation | What to do |
| --- | --- | --- |
| 1 | `tools/` has no `__init__.py`, so a script run as `python tools/xyz.py` cannot see `core` or `sim` by default | `tools/run_scenario.py` starts with a `sys.path.insert(...)` line that fixes this. Copy that pattern for every future tool |
| 2 | `tests/` has no `__init__.py` | Fine. The only rule: every test file name must be unique |
| 3 | `.gitkeep` files stay in `contracts/` | Harmless. Delete if you like |

### 1.3 Gaps I found in the roadmap's Phase 1 text, and how this guide closes them

These are the places where following the roadmap literally would have produced a bug or a dead end.
Each fix is already in the code and covered by a test.

| # | Gap in the original | What would have gone wrong | What this guide does |
| --- | --- | --- | --- |
| G1 | Isolation is verified by "10 windows with no missed heartbeat", but an isolated node is silent on purpose | Isolation could never be verified, so the policy would escalate to Critical every time | While `isolated` is true, a missing heartbeat is ignored (`core/policy.py`, `Context.isolated`) |
| G2 | Drift ends in "flag sensor, trust 0", but every action is verified and escalated | Flagging does not make drift go away, so verification fails and the policy would isolate a node that is only flagged | Actions are split into **corrective** (restart, isolate, rollback, safe mode: verified and escalated) and **informational** (flag sensor, lower trust, increase monitoring: never verified) |
| G3 | The test-burst context ends when the burst ends | Burst frames stay inside the 1 s window for another second, so the flood monitor fires right after every burst | The context stays active for burst duration **plus the window length** (`Supervisor.start_test_burst`) |
| G4 | The default scenario has a flood at 60 s, a hang at 90 s, and so on, but after a flood the node stays isolated forever | Nothing after 60 s could happen | After a verified isolation the node is held for `isolation_hold_s` (10 s), then restored: relay on and hard reset (matches roadmap 4.7 and 6.2) |
| G5 | A firmware deployment makes the node silent while it boots | The heartbeat deadline would fire and the policy would try to "restart" a node that is just booting its new image | `Supervisor.start_deploy` opens a 2 s boot-settling period (roadmap 7.5 already names a 2 s grace). It also emits the contract event `fw_deploy_started` |
| G6 | `periodic()` counts frames with `int((t1 - t0) / period)` | Floating point can give 2 instead of 3 (`0.3 / 0.1` is `2.9999999999999996`) | The simulator runs in fixed 10 ms ticks and never divides times |
| G7 | The simulator is open-loop (it returns a finished list of frames) but the node must react to gateway commands | Soft reset, hard reset, isolation and rollback could not change the traffic | `VehicleSim` is stepped every 100 ms and accepts commands, exactly like the real node |
| G8 | Features use list order for gaps | With timing jitter, frames of the same ID can be slightly out of order, giving a wrong (even negative) gap | Gaps are computed on **sorted** times |
| G9 | The node list says states BOOT, RUN, CANARY, SAFE, SILENT, HUNG, but the contract has only four state codes | Dashboard and firmware would disagree about what a hung node reports | SILENT and HUNG exist only inside the simulator. The gateway reports **MISSING** in telemetry when the heartbeat is overdue (recorded in `contracts/telemetry_schema.md`) |
| G10 | "Flood" at 1500 frames/s is only 33 % bus load | On a real bus this does not starve other IDs. Starvation needs a saturated bus (the node sending as fast as it can) | The simulator adds the frames as specified and does **not** model arbitration starvation. Phase 6 measures the real behaviour. Do not claim starvation from the simulation |

One more lesson from the tests: `(1.3 - 1.0) * 1000` is `300.00000000000006` in Python, so "age greater than 300 ms"
fired at exactly 300 ms. `HeartbeatMonitor.missed` now has a tiny margin. This is why the roadmap insists on
"just under and just over" tests.

---

## 2. Prerequisites for Phase 1

### 2.1 What you must already have (from Phase 0)

| Item | Check | Expected |
| --- | --- | --- |
| Repository cloned, you can pull and push | `git status` | "nothing to commit" or a clean list |
| Python 3.12 (3.10 or newer should work; only 3.12.3 was tested) | `python --version` (`python3 --version` on macOS/Linux) | `Python 3.12.x` |
| Virtual environment active | your prompt starts with `(.venv)` | yes |
| Packages installed | `python tools/check_env.py` | ten lines starting `OK` |
| Arduino IDE and boards | **not needed in Phase 1** | skip |

### 2.2 Install nothing new

Phase 1 uses only `numpy` and `pytest` (plus the Python standard library: `json`, `struct`, `dataclasses`, `collections`).
If `python tools/check_env.py` passed in Phase 0, you are ready.

### 2.3 Knowledge to have (read first, 1 to 2 hours)

| Topic | You are ready when you can... |
| --- | --- |
| CAN IDs and priority | Explain why 0x050 beats 0x100 in arbitration |
| Python classes and dataclasses | Read `class NodeSim` and say what `self` is |
| Mean and standard deviation | Say what a large standard deviation of heartbeat gaps means |
| `pytest` | Write `def test_x(): assert 1 + 1 == 2` and run it |
| Git branches | `git checkout -b phase1-core`, commit, push, open a pull request |

---

## 3. What you will build

### 3.1 File map

| File | Roadmap step | Purpose |
| --- | --- | --- |
| `contracts/can_catalogue.md`, `telemetry_schema.md`, `harness_commands.md`, `api.md` | 1.1 | The four frozen contracts |
| `contracts/examples/telemetry.json`, `event.json` | 1.1 | Machine-checked examples of the message shapes |
| `core/config.json`, `core/config.py` | 1.7, 1.8 | Every threshold in one place |
| `core/frames.py` | 1.2 | The `Frame` record: (time, id, dlc, data) |
| `core/catalogue.py` | 1.1 | Catalogue constants in code |
| `core/can_codec.py` | 1.2 | Encode and decode the 8-byte payloads |
| `core/features.py` | 1.6 | The six features and the bus-load estimate |
| `core/monitors.py` | 1.7 | Heartbeat deadline, per-ID rate, sensor drift |
| `core/policy.py` | 1.8 | Policy table, verify, escalate, cooldown, restore |
| `core/supervisor.py` | 1.6 to 1.8 | One loop: frames in, severity and action out |
| `sim/params.py` | 1.3 | Simulator numbers (placeholders until Phase 4) |
| `sim/vehicle_sim.py` | 1.2 to 1.5 | Healthy traffic, node state machine, four faults, gateway actions, sensors |
| `sim/scenarios.py` | 1.9 | Scenario format and ground truth |
| `sim/runner.py` | 1.9 | Closed-loop runner: simulator plus supervisor |
| `tools/run_scenario.py` | 1.9 | Command line: run a scenario, print the timeline |
| `tests/test_*.py` (8 files, including your existing `test_smoke.py`) | 1.10 | 81 tests |

### 3.2 How the pieces fit

```
 VehicleSim (sim/)                     Supervisor (core/)
 ------------------                    ----------------------------------------------
 healthy traffic + faults   frames     rolling buffer -> features (6 numbers)
 node state machine     ------------>  heartbeat monitor | rate monitor | drift monitor
 reference IMU          ref samples    -> flags -> policy table -> verify / escalate
        ^                                          |
        |          action (soft reset, hard reset, isolate, rollback...)
        +------------------------------------------+
```

The supervisor never looks inside the simulator. It sees **frames and reference samples only**, exactly what the
real gateway will see. That is what makes the later firmware port a fair comparison.

---

## 4. Step by step

Run every command from the repository root, with the virtual environment active.

### Step 0: Branch, copy the files, first test run

```bash
git checkout main
git pull
git checkout -b phase1-core
```

Unzip `autoshield_phase1.zip` and copy **everything inside its `autoshield` folder** into your clone
(say yes to overwrite `README.md`). Make sure the `core`, `sim`, `contracts`, `tests` and `tools` folders merged
rather than replaced (your existing files in them must still be there).

```bash
python -m pytest -q
```

**Pass:** `81 passed` (the time varies, about 3 seconds). If you see an `ImportError`, you are not in the repository root.

### Step 1 (roadmap 1.1): Read and freeze the contracts

The four files in `contracts/` are copies of roadmap Section 5, plus the Phase 1 decisions.

1. Read `contracts/can_catalogue.md` and `contracts/telemetry_schema.md` slowly. Everything else depends on them.
2. Send R1 the CAN catalogue to check: 8-byte payloads, achievable rates. Send R2/R4 the telemetry schema to check that
   it has every field the screens and the features need.
3. Run `python -m pytest tests/test_contracts.py -q`. It parses the two JSON examples and checks them against the code.
4. When every teammate has replied "read, agree", tag:

```bash
git add contracts
git commit -m "contracts v1"
git tag contracts-v1
```

From now on a contract change needs a version bump and a message to the whole team.

**Gate:** tagged `contracts-v1`, every member confirmed.

### Step 2 (1.2): Frame model, catalogue, codec, config

* `core/frames.py`: a frame is `Frame(t, can_id, dlc, data)`. It is a `NamedTuple`, so `f[0]` is the time and `f[1]` is the ID.
* `core/catalogue.py`: IDs, expected rates (10 + 10 + 1 + 50 = 71 frames per second), command codes, state codes.
* `core/can_codec.py`: packs and unpacks the payloads with Python's `struct`. The `<` in each format means little-endian,
  which is exactly the contract's byte order.
* `core/config.json`: every threshold. Phase 5 will generate the firmware header from this same file.

Try it in a Python prompt (`python`):

```python
from core import can_codec as c
data = c.encode_imu(-1234, 0, 0, 1000)
print(data.hex(), c.decode_imu(data))
```

**Check:** `python -m pytest tests/test_codec.py -q` passes (4 tests).

### Step 3 (1.3): Healthy traffic

`sim/vehicle_sim.py` generates the healthy bus. Each message has a nominal send time (k times the period) plus a little
random jitter. The generator is **seeded**: the same seed always gives the same traffic, which makes every test repeatable.

```python
from sim.vehicle_sim import VehicleSim
sim = VehicleSim(seed=1)
frames, ref = sim.advance(60.0)       # 60 simulated seconds
print(len(frames) / 60)               # about 70.9 frames per second
```

**Check:** `python -m pytest tests/test_sim.py -q -k "healthy or same_seed or small_steps"` passes.

**What to look at:** `sim/params.py`. The jitter numbers (0.5 ms, 0.3 ms) are placeholders. In Phase 4 you replace them with
the standard deviations measured from the real CAN log.

### Step 4 (1.4): The node state machine and the four faults

`NodeSim` has the states BOOT, RUN, CANARY, SAFE and HUNG. Isolation is a relay on the bus (the `isolated` flag in `VehicleSim`).

| Fault | How to inject | What the simulator does |
| --- | --- | --- |
| CAN flooding | `sim.inject("flood", duration_s=10)` | Adds 1500 frames/s of ID 0x050 |
| ECU dropout | `sim.inject("hang")` | Node stops sending and ignores CAN commands until a hard reset. `boots=2` makes it hang again after the next two reboots |
| Sensor drift | `sim.inject("drift", slope=50)` | Offset on gyro_z grows by 50 centi-deg/s every second |
| Faulty firmware | `sim.deploy("faulty")` or `sim.inject("faulty_fw")` | Node reboots into the other bank as CANARY. After 3 s it sends bursts of ID 0x3A0 (not in the catalogue) and its heartbeat timing becomes erratic |

Gateway actions: `SOFT_RESET`, `SILENCE`, `RESUME`, `FW_COMMIT`, `FW_ROLLBACK`, `TEST_BURST`, `SAFE_MODE` (all travel as a
0x010 frame on the bus) and `HARD_RESET`, `ISOLATE`, `RESTORE` (hardware lines, not on the bus):

```python
sim.command("SOFT_RESET")
sim.command("TEST_BURST", ms=2000)
```

Two realistic details are built in: a hung node cannot hear a soft reset, and **a reset before a new image is confirmed rolls
back to the old image** (this is what the bootloader does on the real ESP32, roadmap Section 7).

**Check:** `python -m pytest tests/test_sim.py -q` passes (15 tests).

### Step 5 (1.5): Sensors

The true motion is a gentle sine (amplitude 500 centi-deg/s, period 20 s). The node reports truth + noise (+ drift). The
reference IMU, which belongs to the gateway and is never on the CAN bus, reports truth + noise. Drift is therefore detected by
comparing the two, which is exactly what the hardware will do in Phase 8.

**Check:** the test `test_drift_offset_grows_linearly_against_reference` passes.

### Step 6 (1.6): Feature extractor

Every 100 ms, look at the last 1 second of frames (half-open: `t_end - 1 <= t < t_end`) and compute six numbers, in this order:
`total_rate, dominance, hb_gap_mean_ms, hb_gap_std_ms, imu_gap_mean_ms, imu_gap_std_ms`. The order is part of the contract.

| Healthy bus | Value |
| --- | --- |
| total_rate | about 71 |
| dominance | about 0.70 (the IMU is the busiest message) |
| heartbeat gap mean / std | about 100 ms / under 1 ms |
| IMU gap mean / std | about 20 ms / under 1 ms |

**Important:** dominance is 0.70 when healthy, so "dominance above 0.5 means flood" is wrong. That is why flooding is detected
by the per-ID rate monitor.

**Check:** `python -m pytest tests/test_features.py -q` passes (6 tests, including a trace you can verify by hand).

### Step 7 (1.7): The three monitors

| Monitor | Rule (starting values in `core/config.json`) | Catches |
| --- | --- | --- |
| Heartbeat deadline | Last 0x100 frame older than 300 ms | ECU dropout |
| Per-ID rate | An ID over 3 times its expected rate (or over 20 per second if it has no expected rate), in 3 windows in a row. 0x1F0 is ignored during a gateway-started test burst | CAN flooding |
| Sensor drift | EWMA of (node gyro_z minus reference gyro_z). Warn above 10, fault above 20 centi-deg/s, for 5 windows in a row | Sensor drift |

*EWMA* means exponentially weighted moving average: `new = 0.9 * old + 0.1 * latest`. It smooths noise so one noisy sample
cannot cause an alarm.

The SVM arrives in Phase 2. Until then, `anomaly` is always `False`. Detection will be hybrid: the SVM for general behaviour
plus these deterministic monitors.

**Check:** `python -m pytest tests/test_monitors.py -q` passes (10 tests, each threshold tested just under and just over).

### Step 8 (1.8): The policy

`core/policy.py` has two layers:

1. `classify(flags, ctx, ...)` is the **policy table** from the roadmap. First match wins:

| # | Condition | Severity | Action |
| --- | --- | --- | --- |
| 1 | Node state CANARY and (anomaly or heartbeat missed or flood) | CRITICAL | FW_ROLLBACK |
| 2 | Flood and no test burst | HIGH | ISOLATE |
| 3 | Heartbeat missed | MEDIUM | RESTART (soft reset, then hard reset after 1 s) |
| 4 | Drift above the fault limit | MEDIUM | FLAG_SENSOR (trust 0) |
| 5 | Drift above the warn limit | LOW | LOWER_TRUST |
| 6 | Anomaly for 3 windows (Medium after 5 s) | LOW / MEDIUM | INCREASE_MONITORING / RESTART |
| 7 | Test burst active | NORMAL | continue |
| 8 | Otherwise | NORMAL | continue |

   The flood row is **before** the heartbeat row on purpose: a flood starves the heartbeats, so a flood also looks like a
   missing heartbeat. Isolate the cause, not the symptom.

2. `PolicyEngine` wraps the table in a state machine:

```
MONITORING --corrective action--> VERIFYING --10 clean windows--> COOLDOWN --> MONITORING
                                      |                 (after ISOLATE: ISOLATED_HOLD 10 s, then RESTORE)
                                      +--deadline passed--> escalate: RESTART -> ISOLATE -> SAFE_MODE -> LATCHED
```

Verification time: 3 s for isolation, 5 s for restart, rollback and safe mode (they reboot the node).

**Check:** `python -m pytest tests/test_policy.py -q` passes (27 tests: every table row, the restart ladder, escalation, cooldown, auto-recovery off).

### Step 9 (1.9): Scenario runner and ground truth

`sim/scenarios.py` holds the scripted run as a list of timed events:

```python
DEFAULT_SCENARIO = [
    (60.0,  "flood",      {"duration_s": 10.0}),
    (90.0,  "hang",       {}),
    (120.0, "drift",      {"slope": 50.0}),
    (140.0, "clear",      {}),
    (150.0, "faulty_fw",  {}),
    (170.0, "test_burst", {"duration_s": 2.0}),
]
```

`clear` (ends the drift) and `test_burst` are two additions to the roadmap's script: the first keeps the faults independent,
the second shows the context-aware behaviour. `ground_truth(...)` returns what really happened, so detection latency
and false alarms can be computed later.

Run it:

```bash
python tools/run_scenario.py
```

Expected output (the times are repeatable because the seed is fixed):

```
 time (s)  event            severity  detail
------------------------------------------------------------------------
     60.0  BENCH                      bench: flood {'duration_s': 10.0}
     60.3  fault_detected   HIGH      flood
     60.3  action_taken     HIGH      isolate
     62.2  verify_ok        HIGH      isolate
     72.2  node_restored    NORMAL    relay on, hard reset
     90.0  BENCH                      bench: hang {}
     90.2  fault_detected   MEDIUM    heartbeat_missed
     90.2  action_taken     MEDIUM    soft_reset
     91.2  action_taken     MEDIUM    hard_reset
     92.8  verify_ok        MEDIUM    restart
    120.0  BENCH                      bench: drift {'slope': 50.0}
    121.5  sensor_flagged   MEDIUM    trust=0
    150.0  BENCH                      bench: faulty_fw {}
    150.0  fw_deploy_started NORMAL    canary
    153.8  fault_detected   CRITICAL  canary_unhealthy
    153.8  action_taken     CRITICAL  fw_rollback
    155.5  verify_ok        CRITICAL  fw_rollback
    170.0  test_burst_started NORMAL   2 s
    172.0  test_burst_ended NORMAL
```

(The real output has a few more lines, for example `severity_change`; they are left out here for space.)

How to read it: each fault is **detected** within a fraction of a second, an **action** is taken, the action is **verified**,
and the test burst at 170 s produces no alarm. Other options:

```bash
python tools/run_scenario.py --seed 7 --duration 120
python tools/run_scenario.py --no-auto-recovery     # detect and report only; the flood is never stopped
```

**Check:** `python -m pytest tests/test_scenarios.py -q` passes (13 tests).

### Step 10 (1.10): The whole test suite

```bash
python -m pytest -q
```

**Pass:** `81 passed`. Every test must pass before the Phase 1 gate. A test that passes only sometimes means a random
generator was not seeded.

### Step 11: Team review and handoffs

| Who | What they check | Where |
| --- | --- | --- |
| R1 | The CAN catalogue is possible on the hardware (8-byte payloads, rates, the 0x1F0 burst) | `contracts/can_catalogue.md` |
| R2 / R3 | Every feature can be computed from the catalogue | `core/features.py` |
| R4 | The telemetry has every field the screens need; paper wireframes of the landing page and dashboard exist | `contracts/telemetry_schema.md` |
| R3 | Hands the frozen contracts to everyone | tag `contracts-v1` |

### Step 12: Commit, push, pull request

```bash
git status
git add .
git commit -m "Phase 1: contracts, simulator, features, monitors, policy, scenario runner, tests"
git push -u origin phase1-core
```

Open a pull request on GitHub. Another person reviews and merges. After the merge:

```bash
git checkout main
git pull
git tag phase1-done
git push origin phase1-done
```

---

## 5. Phase 1 checklist (definition of done)

| Roadmap checklist item | Proved by |
| --- | --- |
| Contracts are frozen and tagged `contracts-v1` | `git tag` (Step 1) and `tests/test_contracts.py` |
| A 5 minute healthy run gives about 71 frames per second | `test_healthy_rate_is_about_71_fps` |
| Each of the four faults can be injected on a schedule | `tests/test_sim.py` and `test_scenarios.py` |
| The heartbeat monitor flags a hung node within the deadline plus one window | `test_hang_detected_within_deadline_plus_one_window...` |
| The rate monitor flags a flood within a few windows and does not fire on normal traffic | `test_rate_*`, `test_flood_detected_...` |
| The drift monitor stays quiet on healthy data and flags a growing offset | `test_drift_quiet_on_noise`, `test_drift_flagged_and_quiet_after_clear` |
| The policy gives the right severity and action for each row | `test_policy_table_rows` (14 cases) |
| Escalation works | `test_escalation_restart_to_isolate_to_safe_mode_to_latched` |
| The scenario runner prints a readable timeline | `python tools/run_scenario.py` (Step 9) |
| All pytest tests pass, results committed | `python -m pytest -q` shows `81 passed` |
| R4 has paper wireframes | Ask R4 (cannot be tested by code) |

- [ ] All of the above ticked
- [ ] `phase1-done` tagged

---

## 6. Common problems

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'core'` when running a tool | Run from the repository root, and keep the `sys.path.insert` line at the top of the tool |
| `ModuleNotFoundError: No module named 'numpy'` | The virtual environment is not active (no `(.venv)` in the prompt) |
| pytest says `no tests ran` | You are not in the repository root, or `pytest.ini` is missing |
| A test passes sometimes and fails sometimes | An unseeded random generator. Use `np.random.default_rng(seed)` |
| Everything is flagged on healthy traffic | The simulator's noise is smaller than the thresholds assume. Print the distributions |
| The policy flaps between states | Missing cooldown or debounce |
| A copied file did not overwrite the old one | Close the file in your editor and copy again |

---

## 7. What to say about Phase 1 at a review

* "Detection is hybrid: rule-based monitors catch dropout, flooding and drift; the SVM (Phase 2) catches general behavioural anomalies."
* "The policy is context aware: the same burst of frames is a flood when injected and normal when the gateway commanded it."
* "Every action is verified, and if verification fails the policy escalates."
* "These results are from simulation with placeholder noise; we re-measure on hardware."

## 8. Handoff to Phase 2

Phase 2 (machine learning and backend) builds directly on this code:

* R2 trains the One-Class SVM on healthy windows produced by `VehicleSim` and `core/features.py`, and plugs its flag into
  `Supervisor.step(...)` (the `anomaly` flag is hard-wired to `False` today).
* R3 wraps `Supervisor` in the virtual gateway: it builds the telemetry message from `StepResult` and publishes it on the WebSocket.
* The contracts must not change without a version bump.
