# AutoShield, Phase 2: Machine Learning and Backend Core

A step-by-step guide for the person doing Phase 2. Beginner friendly: follow the steps in
order, run the check after every step, and do not move on until the check passes.

- **Goal:** a trained and evaluated One-Class SVM with a `model.json` file, plugged into the
  Phase 1 supervisor, and a FastAPI server that streams simulated telemetry over WebSocket and
  stores events in SQLite.
- **Lead:** R2 (machine learning) and R3 (backend). **Effort:** 7 to 10 days. **Depends on:** Phase 1. **Deferrable:** no.
- **Why it matters:** the model must exist before the firmware can port it (Phase 5). The backend
  must exist before the dashboard can show anything (Phase 3).

---

## 0. What was tested, and what was not

| Tested by running it (Linux, Python 3.12.3, numpy 2.4.4, scikit-learn 1.8.0, fastapi 0.158.2, uvicorn 0.54.0, starlette 1.9.0, httpx 0.28.1, pytest 9.1.1) | Not tested (do these on your machine) |
| --- | --- |
| The 43 new Phase 2 tests pass (39 pass and 4 skip until a model is trained). The dataset builds in about 30 s. Training, export and the "manual formula equals scikit-learn" proof (difference about 7e-15). The full Phase 1 scenario with the SVM plugged in. 5 x 10 minutes of fresh healthy traffic with the SVM: zero alarms. The server under a real `uvicorn` process: `/`, `/dashboard/`, `/api/*`, the WebSocket, inject, CSV export. `tools/metrics.py`, `tools/make_sample_run.py`. | Windows and macOS commands. A browser looking at the Phase 2 test page. **Your 81 Phase 1 tests were not re-run by me** (I rebuilt Phase 1 from your files and checked that the scenario timeline is identical to your Step 9 output: 60.3, 62.2, 72.2, 90.2, 91.2, 92.8, 121.5, 153.8, 155.5). My edits to Phase 1 files are small and additive (Section 2), but run `python -m pytest -q` and confirm. |

Every number in this guide comes from **simulation** with placeholder noise. Phases 4 and 5 replace the guesses with real data.

---

## 1. Hands-on review of the code and the roadmap

I read every file you attached: the roadmap, README, all of `core/`, `sim/`, `contracts/`, `tools/`, `tests/`, `docs/`, the sketches and the config.

### 1.1 What is already right (reuse it, do not rewrite it)

| Item | Why it matters for Phase 2 |
| --- | --- |
| `core/features.py` and `Supervisor.step()` | The **same** code path will produce training features and run-time features, so they can never disagree. `ml/dataset.py` reuses it through `run_closed_loop`. |
| `Supervisor` never looks inside the simulator | The virtual gateway can be a fair copy of the real gateway. It decodes the node state from frames, exactly like the firmware will. |
| `Flags.anomaly` already exists in the policy | The SVM only has to set one boolean. |
| `core/config.json` as the single source of thresholds | Untouched. The SVM threshold lives in `model.json` and is exported to the firmware header in Phase 5. |
| `pytest.ini` with `pythonpath = .` | Lets `tests/` import `core`, `sim`, `ml`, `backend`. |
| `requirements.txt` | **Already contains everything Phase 2 needs.** No new packages. |

### 1.2 Gaps I found, and how this guide closes them

Gaps G1 to G10 are in `docs/phase1_roadmap.md`. These are new (numbering continues). Each fix is in the code and covered by a test.

| # | Gap | What would have gone wrong | Fix |
| --- | --- | --- | --- |
| G11 | `Supervisor` hard-wires `anomaly=False`; there is no way to plug a model in | Nothing could use the SVM | `Supervisor(detector=...)`. With `detector=None` behaviour is exactly Phase 1. `StepResult` gets two new fields at the end (`anomaly_score`, `anomaly_raw`) so old code still works |
| G12 | An **isolated** node is silent on purpose, but the SVM sees "silent node" features as anomalous | Isolation verification needs 10 clean windows, so with an SVM it would **never verify** and would escalate to Safe Mode every time | The anomaly flag is ignored while the node is isolated (same idea as Phase 1 gap G1 for heartbeats) |
| G13 | A node booting a new image is silent for about 0.5 s; the Phase 1 grace period only covers "heartbeat missed" | The SVM flags the boot gap while the node already reports CANARY, and policy row 1 would **roll back even a good update** | The 2 s boot-settling grace (roadmap 7.5) now also covers the SVM anomaly |
| G14 | The anomaly streak kept counting during a gateway-started test burst (the SVM does flag a burst) | After the burst the streak is already "50+", so one stray window would trigger an instant Medium restart | `core/policy.py`: the streak is not counted while `ctx.test_burst` is true |
| G15 | `run_closed_loop` cannot vary the simulator noise or take a detector | Roadmap 2.1 asks for runs with "slightly different timing noise" | Two optional arguments: `detector` and `sim_params` |
| G16 | The roadmap says `app.mount('/', StaticFiles(directory='web'))`, but `web/` has no pages in Phase 2, and a relative directory breaks when you start the server from another folder | The Phase 2 checklist item "`/` serves a page" could not pass | The path is built from the file location, and two small placeholder pages are provided (`web/index.html`, `web/dashboard/index.html`). R4 replaces them in Phase 3 |

Two honest findings from the results, worth saying out loud at a review:

1. **The SVM cannot see sensor drift.** The six features describe timing and rates, not the IMU values. Drift is caught only by the drift monitor. The SVM table shows "0 of 4 detected" for drift. That is correct and is exactly why detection is hybrid.
2. **The SVM flags a gateway-started test burst**, and the **context rule** is what keeps the severity Normal. This is the live proof of "context aware" (test `test_svm_sees_the_flood_and_the_test_burst_but_context_suppresses_the_burst`).

### 1.3 Smaller notes

- `uvicorn[standard]` is what gives you WebSocket support. Plain `uvicorn` will refuse WebSocket connections.
- A harmless `StarletteDeprecationWarning` about `httpx` appears when running the API tests. It does not affect results.
- `StandardScaler` and `OneClassSVM` come from scikit-learn, but **scikit-learn is not needed to run the detector**; `core/model.py` needs only numpy. The firmware port in Phase 5 follows `core/model.py`.
- `pandas` is installed (Phase 1 requirements) but Phase 2 does not need it.

---

## 2. What changed in Phase 1 files (4 small edits, all backwards compatible)

| File | Change |
| --- | --- |
| `core/supervisor.py` | `detector=None` argument; two new fields at the end of `StepResult`; SVM flag gated by boot grace and isolation (G11 to G13) |
| `core/policy.py` | One line: the anomaly streak is not counted during a test burst (G14) |
| `sim/runner.py` | `run_closed_loop(..., detector=None, sim_params=None)` (G15) |
| `tools/run_scenario.py` | New `--svm` option |

Nothing in `contracts/` changed, so `contracts-v1` stays valid. Section 9 lists three clarifications to add to the contract text (they change no field).

---

## 3. Prerequisites

### 3.1 You must already have (from Phases 0 and 1)

| Item | Check | Expected |
| --- | --- | --- |
| Repository cloned, Phase 1 merged | `git status` then `git log --oneline -3` | clean, Phase 1 commit visible |
| Python 3.12 (3.10+ should work) | `python --version` | `Python 3.12.x` |
| Virtual environment active | prompt starts with `(.venv)` | yes |
| Packages installed | `python tools/check_env.py` | ten lines starting `OK` |
| Phase 1 tests pass | `python -m pytest -q` | `81 passed` |

### 3.2 Install nothing new

Phase 2 uses `numpy`, `scikit-learn`, `fastapi`, `uvicorn[standard]`, `websockets`, `httpx` and `pytest`, all already in `requirements.txt`. If `check_env.py` passed in Phase 0, you are ready. **No Arduino IDE and no hardware** are needed.

### 3.3 Knowledge to have (read first, 2 to 3 hours)

| Topic | You are ready when you can... |
| --- | --- |
| Training vs testing vs validation | Say why we pick `nu` and `gamma` on validation runs and look at the test runs only once |
| Data leakage | Say why windows of one run must never be split across train and test |
| One-Class SVM idea | Say it learns "what normal looks like" from healthy data only, and what `nu` and `gamma` do |
| False positive vs false negative | Give one example of each on this project |
| REST vs WebSocket | Say which one carries data to the browser and which carries commands |
| JSON | Read the example in `contracts/examples/telemetry.json` |
| `async` basics (optional) | Say why a slow function must not run directly inside an `async` function |
| SQL basics (optional) | Read `SELECT * FROM runs` |

---

## 4. What you will build

### 4.1 File map (new files marked NEW, edited files marked EDIT)

```
autoshield/
  README.md                          EDIT  prerequisites and Phase 2 commands
  core/
    model.py                         NEW   the SVM evaluated by hand (numpy only)
    supervisor.py                    EDIT  detector hook
    policy.py                        EDIT  streak rule (G14)
  sim/
    runner.py                        EDIT  detector and sim_params
  ml/
    dataset.py                       NEW   makes ml/data/raw/features.npz
    evaluation.py                    NEW   false-positive and latency helpers
    grid_search.py                   NEW   choose nu and gamma on VALIDATION runs
    train.py                         NEW   fit, export model.json, prove the maths
    evaluate.py                      NEW   results note (validation or test)
    models/model.json                made by you (commit it)
    data/raw/features.npz            made by you (ignored by Git, about 4 MB)
  backend/
    telemetry.py                     NEW   builds the contract telemetry message
    gateway.py                       NEW   the virtual gateway (sim + supervisor + SVM)
    hub.py                           NEW   WebSocket broadcast
    store.py                         NEW   SQLite: runs, telemetry, events, CSV export
    main.py                          NEW   FastAPI app and endpoints
  web/
    index.html                       NEW   placeholder landing page (R4 replaces in Phase 3)
    dashboard/index.html             NEW   raw-stream test page (R4 replaces in Phase 3)
    assets/sample_run.jsonl          made by you with tools/make_sample_run.py
  tools/
    run_scenario.py                  EDIT  --svm
    metrics.py                       NEW   latency and false alarms against ground truth
    make_sample_run.py               NEW   saves a run for the dashboard replay mode
  tests/
    test_model.py  test_dataset.py  test_svm_loop.py
    test_gateway.py  test_store.py  test_api.py              NEW (43 tests)
  docs/
    phase2_roadmap.md                NEW   this guide
    phase2_results.md                made by you (Step 8)
```

### 4.2 How the pieces fit

```
 VehicleSim --frames--> Supervisor --------------------> Decision (severity, action, events)
 (sim/)                 (core/)                               |
     ^                   features(6) --> SvmModel --> anomaly flag
     |                   monitors (heartbeat, rate, drift) --> flags
     +------- action (soft reset, isolate, rollback...) -------+
                          |
                          v
              VirtualGateway.step() every 100 ms  (backend/gateway.py)
                          |  telemetry + events (contract JSON)
              +-----------+-------------+
              v                         v
        Hub -> WebSocket /ws       Store -> SQLite -> CSV
        (browser dashboard)        (runs, telemetry, events)
```

Training is offline: `ml/dataset.py` makes windows, `ml/train.py` writes `ml/models/model.json`,
and `core/model.py` loads that file at run time.

---

## 5. Step by step

Run every command from the repository root with the virtual environment active.
On macOS and Linux use `python3` only *before* the environment is active; afterwards `python` works.

### Step 0: Branch, copy the files, first test run

```bash
git checkout main
git pull
git checkout -b phase2-ml-backend
```

Unzip `autoshield_phase2.zip` and copy **everything inside its `autoshield` folder** into your clone
(say yes to overwrite `README.md`, `core/policy.py`, `core/supervisor.py`, `sim/runner.py`,
`tools/run_scenario.py`). Make sure folders merged rather than replaced.

```bash
python -m pytest -q
```

**Pass:** `120 passed, 4 skipped` (81 from Phase 1 + 39 new; the 4 skipped tests wait for a trained model).
If you see `ModuleNotFoundError`, you are not in the repository root.

### Step 1: Read the code (1 to 2 hours, do not skip)

Read in this order. For each file, say in one sentence what it does.

1. `core/model.py` (60 lines). The formula in the docstring is the whole SVM.
2. `core/supervisor.py`. Find the three lines that compute `score`, `anomaly_raw` and `anomaly`. Find why `anomaly` also checks `_grace_until` and `isolated` (gaps G12, G13).
3. `ml/dataset.py`. Find `sim_params_for` (different noise per run) and the seed lists (who is train, validation, test).
4. `ml/train.py`. Find `fit` (scale, then train) and `export_model` (the parity proof).
5. `backend/gateway.py`. Follow one call of `step()` from top to bottom.
6. `backend/main.py`. Find `gateway_loop` and the line with `asyncio.to_thread`. Find the `app.mount` line and confirm it is **last**.

**Check yourself:** why is `dominance` useless for flood detection? (Answer: it is already about 0.70 when healthy.)

### Step 2: Try the supervisor hook by hand

```python
python
>>> from sim.runner import run_closed_loop
>>> class Stub:                              # a fake detector: everything is anomalous
...     threshold = 0.0
...     def anomaly_score(self, f): return 1.0
>>> res = run_closed_loop([], 10.0, seed=1, detector=Stub())
>>> [(e["t_ms"], e["kind"], e["detail"]) for e in res.events]
[(1200, 'fault_detected', 'svm_anomaly')]
>>> exit()
```

The first window is evaluated at 1.0 s; the policy needs 3 anomalous windows in a row, so the event is at 1.2 s.

### Step 3 (roadmap 2.1): Generate the datasets

```bash
python -m ml.dataset
```

It simulates 20 healthy runs of 10 minutes (about 3.3 hours of traffic) and fault runs, and saves
`ml/data/raw/features.npz` (about 4 MB, **ignored by Git**, takes about 30 seconds).

| Split | Seeds | Used for |
| --- | --- | --- |
| Train | 12 healthy runs (1000 to 1011) | fit the model |
| Validation | 4 healthy runs + 4 runs per fault (1012 to 1015, 2000 to 2003) | choose `nu` and `gamma` |
| Test | 4 healthy runs + 4 runs per fault (1016 to 1019, 3000 to 3003) | final report, **once** |

Each run has slightly different timing noise (0.8x to 1.5x of the placeholders in `sim/params.py`).
Splits are by whole runs, never by window (data leakage).

**Check:** the script ends with `saved .../ml/data/raw/features.npz`. `python -m pytest tests/test_dataset.py -q` passes (5 tests).
To regenerate: `python -m ml.dataset --force`.

### Step 4 (roadmap 2.3): Choose nu and gamma on validation runs

```bash
python -m ml.grid_search
```

It trains 16 models (4 values of `nu` x 4 values of `gamma`) on every 20th training window and prints,
for each, the support vectors, the false positives on healthy validation runs and whether each fault is detected.

What I got (yours should be close; small differences are normal):

```
    nu   gamma   SVs  flagged %  FP ep/h  flood   hang     fw   latency s (flood/hang/fw)
 0.005  0.0500    29       0.63      0.0 4/  4 4/  4 4/  4              0.30/0.30/0.30
 0.010  0.0500    44       0.83      0.0 4/  4 4/  4 4/  4              0.30/0.30/0.30
 0.020  0.0500    79       1.54     10.5 ...
 0.010  0.5000   459      11.81    252.4 ...
```

How to choose: (1) every fault detected in every run, (2) fewest false-positive episodes per hour
(an episode is 3 or more flagged windows in a row, the policy's rule), (3) few support vectors, because the ESP32
evaluates all of them every 100 ms. **I chose `nu = 0.01`, `gamma = 0.05`** (44 support vectors).
Write your choice and the reason in `docs/decisions.md`. Large `gamma` (0.5) gives about 460 support vectors and
many false alarms: it memorises the training noise.

**Never use the test runs for this step.**

### Step 5 (roadmap 2.2 and 2.4): Train and export the model

```bash
python -m ml.train
```

Expected (numbers may differ slightly):

```
trained on 3600 healthy windows (nu=0.01, gamma=0.05)
support vectors: 44   model.json: 6.6 KB
manual formula vs scikit-learn, largest difference: 7.11e-15  (must be tiny)
written: .../ml/models/model.json
```

The script **refuses to finish** if the hand-written formula and scikit-learn differ by more than 1e-9.
`model.json` holds the feature order, scaler mean and scale, gamma, support vectors, dual coefficients,
intercept, threshold, training date and version. Other settings: `python -m ml.train --nu 0.02 --gamma 0.1 --version 1.1`.

**Check:** `python -m pytest -q` now says `124 passed` (the 4 skipped tests run).
Commit `ml/models/model.json` (it is small).

### Step 6 (roadmap 2.5): Evaluate on validation runs

```bash
python -m ml.evaluate --split val
```

You get the false-positive table and a detection table per fault. Read the drift row: **0 of 4 detected**.
That is expected (see Section 1.2). The test-burst row shows "detected": the SVM does flag it, and the
context rule keeps the severity Normal (Step 7).

### Step 7: See the SVM in the closed loop

```bash
python tools/run_scenario.py --svm
```

Compare with `python tools/run_scenario.py` (no SVM). With the SVM you should see the same story:
flood isolated (60.3 s), hang restarted (90.2 s soft, 91.2 s hard), drift flagged (121.5 s), faulty firmware
rolled back (**152.0 s**, earlier than 153.8 s because the SVM sees the erratic heartbeat as soon as the boot
grace ends), and **no alarm** during the test burst at 170 s.

### Step 8: Final evaluation on the test runs (ONCE)

Only when you will not change the model any more:

```bash
python -m ml.evaluate --split test --write docs/phase2_results.md
```

My result on the test runs (simulation): 44 support vectors, 6.6 KB, **6 false-positive episodes in 0.67 h
(9 per hour)**, flood, hang and faulty firmware detected in 4 of 4 runs with 0.30 s latency, drift 0 of 4.
Note the validation runs had 0 episodes but the test runs had 6: with only 40 minutes of validation data the
estimate is rough. Report the test number, say it is a simulation result, and do **not** go back and tune on it.
These LOW-severity episodes only log and raise monitoring; they never trigger an action unless they last
over 5 s (policy row 6). In the 10-minute closed-loop runs there were zero alarms because no episode reached the policy.
Commit `docs/phase2_results.md`.

### Step 9 (roadmap 2.6 to 2.7): Start the backend

```bash
python -m uvicorn backend.main:app --port 8000
```

Open <http://127.0.0.1:8000/> (placeholder landing page, shows "backend online") and
<http://127.0.0.1:8000/dashboard/> (raw stream test page). `/dashboard` without the slash is redirected to
`/dashboard/`, which is normal. You should see the badge SIMULATION, severity NORMAL, and telemetry updating ten times a second.
Stop the server with Ctrl+C.

Options (environment variables):

| Variable | Meaning | Example (macOS/Linux) | Example (Windows cmd) |
| --- | --- | --- | --- |
| `AUTOSHIELD_SPEED` | simulation speed, 1 = real time | `AUTOSHIELD_SPEED=10 python -m uvicorn backend.main:app --port 8000` | `set AUTOSHIELD_SPEED=10` then the command |
| `AUTOSHIELD_SEED` | random seed of the vehicle | `AUTOSHIELD_SEED=7 ...` | `set AUTOSHIELD_SEED=7` |
| `AUTOSHIELD_DB` | database file | `AUTOSHIELD_DB=my.db ...` | `set AUTOSHIELD_DB=my.db` |

To let another laptop open the page: add `--host 0.0.0.0` and use your laptop's address (allow it in the firewall).
If there is no `ml/models/model.json` the server still starts but runs **without the SVM** (telemetry shows `"model":"none"`).

### Step 10 (roadmap 2.8): Try the API

With the server running, either click the buttons on the dashboard test page, or use Python (works the same on every OS):

```bash
python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/api/health').json())"
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/api/inject', json={'fault':'flood','duration_ms':3000}).json())"
python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/api/events?limit=5').json())"
```

Watch the dashboard test page: severity goes HIGH, an `isolate` action appears, `verify_ok` follows about 2 s later,
and the node is restored about 10 s after that.

| Endpoint | What it does in Phase 2 |
| --- | --- |
| `GET /api/health` | `{"status":"ok"}` |
| `GET /api/state` | latest telemetry (404 until the first message exists) |
| `GET /api/events?limit=100` | recent events (limit 1 to 1000) |
| `POST /api/inject` | `{"fault":"flood" or "hang" or "drift" or "faulty_fw", "duration_ms":.., "slope":..}`. `duration_ms` only for flood (default 5000, max 60000), `slope` only for drift (default 50). Returns 409 if you deploy firmware while the node is hung or booting |
| `POST /api/control` | `{"cmd":"auto_recovery","on":false}`, `{"cmd":"test_burst","ms":2000}`, `{"cmd":"reset_bench"}` (restarts the simulation, time goes back to 0) |
| `GET /api/runs` | recorded runs with telemetry and event counts |
| `POST /api/runs/start` | `{"label":"my run"}` closes the open run and starts a new one |
| `POST /api/runs/stop` | stops recording (nothing is stored until you start a run) |
| `GET /api/export.csv?run_id=1&what=telemetry` | CSV; `what=events` for events |
| `WS /ws` | stream of telemetry (10 per second) and event messages |

`/api/mode`, `/api/ports`, `/api/firmware/deploy` and `/api/metrics` are Phases 5, 7 and 8; they do not exist yet.
The server starts one run labelled `live` automatically, so storage works out of the box.

### Step 11: Look at the database and export a CSV

Stop the server (Ctrl+C) so the file is complete, then:

```bash
python -c "import sqlite3; c=sqlite3.connect('autoshield.db'); print(c.execute('select id,label,start_utc,model_version,git_commit from runs').fetchall()); print(c.execute('select kind,count(*) from events group by kind').fetchall())"
```

Or, while the server runs: open <http://127.0.0.1:8000/api/export.csv?run_id=1> in the browser (it downloads a CSV).
`autoshield.db` is ignored by Git. Every run row stores the model version and the git commit (testing rule: a result without its versions cannot be trusted).

### Step 12 (roadmap 2.9): Command line tools

```bash
python tools/run_scenario.py --svm                        # timeline (done in Step 7)
python tools/metrics.py --svm --seeds 5 --healthy-minutes 30
```

`metrics.py` runs the scripted scenario several times and prints, per fault, the detection latency
(fault start to `fault_detected`), response latency (detection to `action_taken`), recovery latency
(`action_taken` to `verify_ok`), and false alarms. My result with the SVM: flood 0.30 s / 0.00 s / 1.90 s,
hang 0.20 / 0.00 / 3.40, drift detected in 1.18 s (no recovery, by design), faulty firmware 2.00 / 0.00 / 2.50,
and **0 false alarms in 0.5 h of healthy traffic**. Without the SVM the faulty firmware is detected in 3.80 s
and the hang recovers in 2.60 s: the SVM catches the faulty firmware earlier, at the price of a stricter
verification (the anomaly flag needs a clean window before `verify_ok`). Times are simulated seconds and the
simulator's noise is a placeholder, so the spread (sd) is tiny. Phases 6 to 8 reuse this tool with real runs.

Then make the handoff file for R4 (Phase 3 step 3.5):

```bash
python tools/make_sample_run.py
```

It writes `web/assets/sample_run.jsonl` (about 1.2 MB: 1900 telemetry lines and the events of the scripted scenario). Commit it.

### Step 13: Update the contract notes (R3, optional but recommended)

Add the three clarifications from Section 9 to `contracts/telemetry_schema.md`, under a heading "Phase 2 decisions". They change no field, so do not move the tag.

### Step 14: Full test run, commit, push, pull request

```bash
python -m pytest -q
git status
git add .
git commit -m "Phase 2: SVM training and export, supervisor hook, virtual gateway, FastAPI backend, SQLite, tools"
git push -u origin phase2-ml-backend
```

**Pass:** `124 passed`. Open a pull request; another person reviews and merges. After the merge:

```bash
git checkout main
git pull
git tag phase2-done
git push origin phase2-done
```

---

## 6. Phase 2 checklist (definition of done)

| Roadmap checklist item | Proved by |
| --- | --- |
| `model.json` exists with feature order, scaler, gamma, support vectors, dual coefficients, intercept, version | Step 5, `test_exported_json_has_every_field_the_firmware_needs` |
| Manual decision function matches scikit-learn on at least 200 windows | Step 5 output (about 1e-15) and `test_manual_formula_matches_scikit_learn_on_200_plus_windows` |
| False positive rate on held-out healthy simulated runs is measured | Step 8, `docs/phase2_results.md` |
| Every injected fault is flagged and each latency is written down | Step 6 and Step 8 tables (SVM) and Step 12 (whole system). Drift is flagged by the drift monitor, not the SVM |
| Number of support vectors is known and is a few hundred at most | 44 in my run |
| `uvicorn` starts, `/` and `/dashboard/` serve a page, `/api/health` returns ok | Step 9, `test_health_and_static_pages` |
| A WebSocket client receives telemetry that follows the contract exactly | `test_websocket_delivers_contract_telemetry`, `test_telemetry_has_exactly_the_contract_shape` |
| `POST /api/inject` makes the fault appear in the stream and the policy react | Step 10, `test_inject_flood_changes_the_stream_and_the_policy_reacts` |
| Events and telemetry are stored in SQLite and can be exported to CSV | Steps 10 to 11, `tests/test_store.py`, `test_runs_start_stop_and_csv_export` |
| Backend tests pass | `python -m pytest -q` shows `124 passed` |

- [ ] All of the above ticked
- [ ] `ml/models/model.json`, `docs/phase2_results.md`, `web/assets/sample_run.jsonl` committed
- [ ] Choice of `nu` and `gamma` written in `docs/decisions.md`
- [ ] `phase2-done` tagged

---

## 7. Common problems

| Problem | Fix |
| --- | --- |
| `4 skipped` in pytest | The model is not trained yet. Run Steps 3 and 5 |
| `FileNotFoundError ... features.npz` or empty results | Run `python -m ml.dataset` first (the other scripts also build it automatically) |
| `ModuleNotFoundError: No module named 'ml'` (or `backend`, `core`) | Run from the repository root (the folder with `pytest.ini`), and use `python -m ml.train`, not `python ml/train.py` |
| `ModuleNotFoundError: No module named 'sklearn'` | Virtual environment not active, or packages not installed (README Section 3) |
| WebSocket "no supported WebSocket library" or connection refused | You installed plain `uvicorn`. Run `pip install -r requirements.txt` (it has `uvicorn[standard]`) |
| `/api/...` returns the landing page | `app.mount("/", ...)` was moved above the routes. It must be last |
| `Address already in use` | Another server holds port 8000. Stop it, or use `--port 8001` |
| Dashboard test page says "offline, retrying" | The server is not running, or you opened the file directly. Open it through `http://127.0.0.1:8000/dashboard/` |
| The page does not open from another laptop | Start with `--host 0.0.0.0`, use the laptop's address, and allow the port in the firewall |
| Very different `nu`/`gamma` results from mine | Different library versions can shift small numbers. Use your own grid output to choose |
| Great validation results but worse test results | Normal with little validation data (my 0 vs 9 per hour). Report the test number honestly |
| Training takes very long | You lowered `--stride`. More windows means more support vectors and slower training and firmware |
| Everything is flagged after you retrain | Wrong model for the simulator noise. Delete `ml/data/raw/features.npz`, regenerate, retrain |
| Tests pass sometimes, fail sometimes | An unseeded random generator in new code. Use `np.random.default_rng(seed)` |
| `database is locked` | Two servers use the same `autoshield.db`. Stop the other one or set `AUTOSHIELD_DB` |

---

## 8. Handoffs

| To | What | Where |
| --- | --- | --- |
| R4 (Phase 3) | Running API and WebSocket, the telemetry contract, `web/assets/sample_run.jsonl` for replay mode, the placeholder pages to overwrite | `backend/`, `contracts/`, `web/` |
| R1 / R2 (Phase 5) | `core/model.py` is the port specification of the SVM; `ml/models/model.json` has every constant; `core/config.json` has every threshold | `core/`, `ml/models/` |
| R3 (Phase 5) | `backend/gateway.py` and `backend/telemetry.py` show exactly what the serial bridge must publish into the hub | `backend/` |

## 9. Contract clarifications (no field changed)

1. `ml.anomaly` in telemetry is the **raw** SVM verdict (`anomaly_score > threshold`). The policy additionally ignores it while the node is isolated or in the 2 s boot-settling grace, and during a test burst; the severity shows the final decision.
2. A node that has had no heartbeat for more than `hb_deadline_ms` is reported as state `MISSING` in `nodes[]`, even while isolated (`isolated` is true then).
3. `run_id` 0 means "not recording"; such telemetry and events are streamed but not stored.

## 10. What to say about Phase 2 at a review

- "The model learns normal behaviour from healthy windows only. We split by whole runs, chose the settings on validation runs, and looked at the test runs once."
- "The SVM is evaluated by hand: the same formula in Python and, in Phase 5, in C++. The two agree with scikit-learn to about 1e-15."
- "Detection is hybrid. The SVM catches flooding, dropout and faulty firmware. It cannot see sensor drift, so a residual monitor does."
- "The SVM does flag a gateway-started test burst, and the context rule keeps the severity Normal."
- "These are simulation results with placeholder noise. We re-measure on hardware."

## 11. Handoff to Phase 3

R4 builds the landing page and dashboard on this backend. R1 starts Phase 4 hardware in parallel. The contracts must not change without a version bump.
