# AutoShield

Embedded safety and health supervisor for autonomous vehicles.
RVCE Experiential Learning project, EC cluster.

AutoShield watches a (simulated or real) CAN bus and catches faults that are
*valid on the wire but wrong in behaviour*: CAN flooding, ECU dropout, sensor
drift and faulty firmware. It decides on a response, acts, and verifies it.

> **Status:** Phases 0 and 1 are done. **Phase 2 (machine learning and backend core)
> is the current phase.** The landing page, dashboard and firmware arrive in later
> phases. This README only promises what exists today; sections marked
> **(later)** describe commands that work once that phase is merged.

---

## 1. Prerequisites: what every teammate needs

### 1.1 Everyone (all roles)

| Item | Version | Why | Check it with |
| --- | --- | --- | --- |
| Git | any recent | version control | `git --version` |
| GitHub account | - | shared repository | you must be added as a collaborator |
| Python | **3.12 recommended** (tested with 3.12.3; 3.10 or newer should work) | simulator, ML, backend, tests | `python --version` (`python3 --version` on macOS/Linux) |
| pip + venv | come with Python | isolated packages | `python -m pip --version` |
| Text editor | VS Code + Python extension is recommended | editing | optional |
| Modern browser | Chrome, Edge or Firefox | test page now, dashboard later | - |
| Disk space | about 1 GB free | Python packages and the generated training data (about 4 MB) | - |
| Internet | needed once | to install packages | - |
| Free network port | 8000 | the backend server | if busy, use `--port 8001` |

**Python packages** (all in `requirements.txt`, installed in Section 3).

| Package | Used for | From phase |
| --- | --- | --- |
| numpy | simulator, features, monitors, the SVM formula | 1 |
| pytest | all tests | 1 |
| scikit-learn | **training** the One-Class SVM (not needed to run it) | 2 |
| fastapi, uvicorn[standard], websockets | backend server and WebSocket | 2 |
| httpx | API tests and the one-line API examples | 2 |
| pandas | not used yet (installed for later analysis) | later |
| python-can, pyserial | serial bridge and virtual CAN bus | 5 |

`uvicorn[standard]` (with the brackets) matters: without it the server refuses WebSocket connections.

**You do NOT need** the Arduino IDE, any board, or any hardware for Phases 1 and 2.

### 1.2 Firmware people only (R1, and R2 for the C++ port later)

| Item | Notes |
| --- | --- |
| Arduino IDE **2.x** | from arduino.cc (needed from Phase 0 hardware work; not for Phase 1 or 2 code) |
| ESP32 board package by Espressif Systems | installed through Boards Manager (Section 5) |
| USB-serial driver | only if no port appears; use a **data** cable |
| Hardware | see `docs/hardware_inventory.md` |

### 1.3 Operating system notes

* **Windows:** use *Command Prompt* or *PowerShell*. When you install Python, tick **Add python.exe to PATH**.
  If `python` is not found, try `py -3.12`. Paths with `/` in commands (for example `python tools/check_env.py`) work on Windows too.
* **macOS / Linux:** use `python3` where this README says `python` *before* the virtual environment is active.
  After activation, `python` works.
* The code was tested on Linux with Python 3.12.3. The Windows and macOS commands are standard but were not run
  by the author: if one fails, see Section 8 and tell the team.

---

## 2. Get the code

```bash
git clone <REPOSITORY URL>
cd autoshield
```

Use the URL from the green **Code** button on GitHub. GitHub no longer accepts
your account password for HTTPS pushes: use the **GitHub Desktop** app, the
**GitHub CLI** (`gh auth login`), or a Personal Access Token when Git asks for
a password.

One-time Git identity (use the same email as your GitHub account):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Already cloned earlier? Update instead:

```bash
git checkout main
git pull
```

---

## 3. Python environment (step by step)

Run every command from the repository root (the folder that contains
`requirements.txt`).

### 3.1 Create the virtual environment (once)

| OS | Command |
| --- | --- |
| Windows | `python -m venv .venv` |
| macOS / Linux | `python3 -m venv .venv` |

Linux only: if that fails with "ensurepip is not available", run
`sudo apt install python3-venv python3-pip` and try again.

### 3.2 Activate it (every new terminal)

| OS / shell | Command |
| --- | --- |
| Windows, Command Prompt | `.venv\Scripts\activate.bat` |
| Windows, PowerShell | `.venv\Scripts\Activate.ps1` |
| macOS / Linux | `source .venv/bin/activate` |

You should now see `(.venv)` at the start of your prompt. If PowerShell says
"running scripts is disabled", run this once in that window and activate again:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`
(or just use Command Prompt).

### 3.3 Install the packages

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the team has already created `requirements.lock.txt`, use it instead so that
everybody has identical versions: `pip install -r requirements.lock.txt`.

### 3.4 Verify (must all say OK)

```bash
python tools/check_env.py
python -m pytest -q
```

Expected:

* `check_env.py`: ten lines starting with `OK`, then "Environment is ready".
  Version numbers may differ from your teammates' (that is fine until the lock file exists).
* `pytest`: **`124 passed`** if the trained model file `ml/models/model.json` is in the repository (it is committed at the end of Phase 2).
  If you see `120 passed, 4 skipped`, the model file is missing: run `git pull`, or train it yourself (Section 4.2).
  A harmless `StarletteDeprecationWarning` about `httpx` may appear; ignore it.
* On a Phase 1 only checkout you will see `81 passed`; on Phase 0 files only, `2 passed`.

If a line says `FAIL` or a test fails, see Section 8.

### 3.5 Lock versions (done once by the team lead, then everyone uses it)

After the whole team's environments work, one person runs:

```bash
pip freeze > requirements.lock.txt
```

and commits it. From then on everyone installs with
`pip install -r requirements.lock.txt`.

---

## 4. Run the project

Everything in this section needs only the Python environment from Section 3. Run from the repository root.

### 4.1 Run the tests

```bash
python -m pytest -q                       # everything
python -m pytest tests/test_policy.py -q  # one file
python -m pytest -q -k flood              # tests with "flood" in the name
```

### 4.2 Phase 2: train the model (R2; teammates can skip if `model.json` is committed)

```bash
python -m ml.dataset          # makes ml/data/raw/features.npz (about 30 s, ignored by Git)
python -m ml.grid_search      # compare nu and gamma on the VALIDATION runs
python -m ml.train            # writes ml/models/model.json (nu 0.01, gamma 0.05 by default)
python -m ml.evaluate --split val
```

`python -m ml.evaluate --split test --write docs/phase2_results.md` is run **once**, at the very end.
Always use `python -m ml.xxx` from the repository root, not `python ml/xxx.py`.

### 4.3 Run the scripted scenario and read the timeline

```bash
python tools/run_scenario.py          # rules only (Phase 1 behaviour)
python tools/run_scenario.py --svm    # with the trained SVM plugged in (Phase 2)
```

It simulates 190 seconds of a vehicle network with four injected faults and a test burst, and prints
what the supervisor did. A healthy-looking result has, in this order: a flood that is detected and
isolated (around 60 s), a hang that is detected and restarted (around 90 s), a drift that is flagged
(around 121 s), a faulty firmware that is rolled back (around 152 to 154 s), and **no alarm** during the test
burst at 170 s.

Options:

```bash
python tools/run_scenario.py --seed 7 --duration 120   # different random seed, shorter run
python tools/run_scenario.py --no-auto-recovery        # detect and report only, never act
```

The same seed always gives the same run, so teammates can compare outputs.

### 4.4 Phase 2: start the backend and open the test page

```bash
python -m uvicorn backend.main:app --port 8000
```

| Open in the browser | You should see |
| --- | --- |
| <http://127.0.0.1:8000/> | placeholder landing page with "backend online" |
| <http://127.0.0.1:8000/dashboard/> | raw live stream test page (badge SIMULATION, severity, buttons to inject faults) |
| <http://127.0.0.1:8000/docs> | automatic API documentation of every endpoint |

Stop with **Ctrl+C**. The real landing page and dashboard replace the two placeholders in Phase 3.

Optional settings (environment variables): `AUTOSHIELD_SPEED` (simulation speed, 1 = real time),
`AUTOSHIELD_SEED`, `AUTOSHIELD_DB`. Windows Command Prompt: `set AUTOSHIELD_SPEED=10`, then start the server.
macOS/Linux: `AUTOSHIELD_SPEED=10 python -m uvicorn backend.main:app --port 8000`.
To open the page from another laptop add `--host 0.0.0.0` and allow port 8000 in the firewall.

Try the API (works on every OS, server running):

```bash
python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/api/health').json())"
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/api/inject', json={'fault':'flood','duration_ms':3000}).json())"
```

Data is stored in `autoshield.db` (ignored by Git). Download a run as CSV from
`http://127.0.0.1:8000/api/export.csv?run_id=1`.

### 4.5 Phase 2: tools

```bash
python tools/metrics.py --svm --seeds 5 --healthy-minutes 30   # latencies and false alarms (simulation)
python tools/make_sample_run.py                                # writes web/assets/sample_run.jsonl for R4
```

### 4.6 Try the simulator by hand

Start `python`, then:

```python
from sim.vehicle_sim import VehicleSim
sim = VehicleSim(seed=1)
frames, ref = sim.advance(10.0)      # simulate 10 seconds
print(len(frames) / 10)              # about 71 frames per second
sim.inject("flood", duration_s=2)    # inject a CAN flood for 2 seconds
```

### 4.7 Where is what

Read `docs/phase1_roadmap.md` and `docs/phase2_roadmap.md` for the step-by-step guides, the design decisions and the checklists.
The four contract files in `contracts/` are the single source of truth for every message; do not change
them without a version bump and a message to the whole team.

---

## 5. Arduino IDE setup (firmware people only)

1. Install Arduino IDE 2.x.
2. **File > Preferences** (macOS: **Arduino IDE > Settings**). In
   *Additional boards manager URLs* paste:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. **Tools > Board > Boards Manager**, search `esp32`, install the one by
   **Espressif Systems**. **Write down the version number** in
   `docs/hardware_inventory.md`; the whole team's firmware uses one version.
4. Boards: classic ESP32 (WROOM-32) = **ESP32 Dev Module**;
   the S3 board = **ESP32S3 Dev Module**.
5. Test sketches live in `firmware/tests/`. Open
   `firmware/tests/hello_serial/hello_serial.ino`, pick board and port, click
   Upload, open Serial Monitor at **115200** baud.
6. Upload will not start? Hold **BOOT**, tap **RESET**, release **BOOT**, retry.
7. No port appears? Change the USB cable first (many are charge-only).
8. Linux: `sudo usermod -a -G dialout $USER`, then log out and back in.

---

## 6. Folder layout

```
autoshield/
  README.md   requirements.txt   pytest.ini   .gitignore
  contracts/   can_catalogue.md, telemetry_schema.md, harness_commands.md, api.md, examples/
  docs/        hardware_inventory.md, pinmap.md, decisions.md, phase0_roadmap.md,
               phase1_roadmap.md, phase2_roadmap.md, phase2_results.md (made in Phase 2)
  sim/         vehicle_sim.py, params.py, scenarios.py, runner.py       simulated vehicle
  core/        config.json, config.py, frames.py, catalogue.py, can_codec.py,
               features.py, monitors.py, policy.py, supervisor.py,
               model.py                                                  reference algorithms + SVM formula
  ml/          dataset.py, evaluation.py, grid_search.py, train.py, evaluate.py,
               models/model.json, data/raw/ (generated, ignored by Git)  machine learning (Phase 2)
  backend/     main.py, gateway.py, telemetry.py, hub.py, store.py       FastAPI server (Phase 2)
               (bridge_serial.py arrives in Phase 5)
  web/         index.html, dashboard/index.html (placeholders now), assets/, vendor/   (Phase 3)
  firmware/    gateway/, target/, shared/, tests/, bin/                  (Phase 0, 4-7)
  tools/       check_env.py, make_layout.py, run_scenario.py, metrics.py, make_sample_run.py,
               later replay/compare/export_header
  tests/       pytest tests: test_smoke, test_codec, test_features, test_sim, test_monitors,
               test_policy, test_scenarios, test_contracts (Phase 1);
               test_model, test_dataset, test_svm_loop, test_gateway, test_store, test_api (Phase 2)
```

Git does not keep empty folders, so each empty folder holds a `.gitkeep` file.
If a folder ever goes missing, run `python tools/make_layout.py` (safe to repeat).

---

## 7. Team workflow

- `main` always works. After the Phase 0 first commit, nobody pushes to it
  directly.
- One branch per task: `git checkout -b r2-features` (role + topic).
- Small commits, then open a pull request; another person reviews and merges.
- Pull before you start work: `git pull`.
- Large raw logs go on the shared drive, **not** in Git. (The generated training data and `autoshield.db` are already ignored.)
- Contract changes (CAN catalogue, telemetry, API) need a version bump and a
  message to the whole team. The current contract is tagged `contracts-v1`.

| Role | Owns |
| --- | --- |
| R1 | Firmware and hardware |
| R2 | Data, ML, simulator, monitors, policy |
| R3 | Repository, contracts, backend, integration |
| R4 | Landing page and dashboard |

Fill in names and backups in `docs/decisions.md`.

---

## 8. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `python` not found (Windows) | Reinstall Python and tick **Add python.exe to PATH**, or use `py -3.12` |
| `FAIL` lines in `check_env.py` | venv not activated (no `(.venv)` in prompt), or `pip install` did not finish; activate and reinstall |
| `externally-managed-environment` error | You are installing outside the venv. Activate `.venv` first; do not use `--break-system-packages` |
| `pytest: command not found` | venv not active; use `python -m pytest` |
| `ModuleNotFoundError: No module named 'core'` (or `sim`, `ml`, `backend`) | You are not in the repository root, or you ran `python ml/train.py`. `cd` to the folder that contains `pytest.ini` and use `python -m ml.train` |
| `ModuleNotFoundError: No module named 'numpy'` or `'sklearn'` | venv not active, or packages not installed (Section 3) |
| pytest says `no tests ran` | You are not in the repository root, or `pytest.ini` is missing |
| `120 passed, 4 skipped` | `ml/models/model.json` is missing. `git pull`, or run Section 4.2 |
| `81 passed` only | Phase 2 files not copied or merged yet |
| Server: "no supported WebSocket library" or WebSocket refused | `uvicorn` installed without `[standard]`. Run `pip install -r requirements.txt` again |
| Server: `Address already in use` | Port 8000 is taken. Stop the other program, or use `--port 8001` |
| Browser test page says "offline, retrying" | Server not running, or you opened the HTML file directly. Use `http://127.0.0.1:8000/dashboard/` |
| `/api/...` shows the landing page | The static-files mount is no longer the last line in `backend/main.py` |
| `database is locked` | Two servers use the same `autoshield.db`; stop one |
| A test passes sometimes and fails sometimes | An unseeded random generator in new code. Use `np.random.default_rng(seed)` |
| Different results on different laptops | Different package versions; use `requirements.lock.txt` |
| Upload fails / port vanishes | Bad cable, or another program (e.g. Serial Monitor) holds the port |
| Two boards, unsure which port is which | Unplug one; the port that disappears is that board. Or run `hello_serial`, which prints the chip model |

---

## 9. Running the full system

Works now (Phase 2): backend, API, WebSocket, test page, simulation with the SVM.
Not yet: the real landing page and dashboard (Phase 3), hardware mode (Phase 5).

```bash
python -m uvicorn backend.main:app --port 8000
# landing page (placeholder): http://127.0.0.1:8000/
# dashboard (test page):      http://127.0.0.1:8000/dashboard/
```

All thresholds in the project are starting values to be tuned from data, not
measured results. Everything printed by the simulator, the model evaluation and the backend is
simulation, not hardware.
