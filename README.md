# AutoShield

Embedded safety and health supervisor for autonomous vehicles.
RVCE Experiential Learning project, EC cluster.

AutoShield watches a (simulated or real) CAN bus and catches faults that are
*valid on the wire but wrong in behaviour*: CAN flooding, ECU dropout, sensor
drift and faulty firmware. It decides on a response, acts, and verifies it.

> **Status:** Phase 0 (foundations and environment) is the current phase.
> The simulator, backend, dashboard and firmware arrive in later phases, so
> this README only promises what exists today. Sections marked **(later)**
> describe commands that will work once that phase is merged.

---

## 1. What you need before you start (prerequisites)

### Everyone (all roles)

| Item | Version | Why | Check it with |
| --- | --- | --- | --- |
| Git | any recent | version control | `git --version` |
| GitHub account | - | shared repository | must be added as collaborator |
| Python | **3.12 recommended** (tested with 3.12.3) | simulator, ML, backend | `python --version` (`python3 --version` on macOS/Linux) |
| pip + venv | come with Python | isolated packages | `python -m pip --version` |
| Modern browser | Chrome, Edge or Firefox | dashboard (later) | - |
| VS Code + Python extension | optional | editing | - |

### Firmware people only (R1, and R2 for the C++ port later)

| Item | Notes |
| --- | --- |
| Arduino IDE **2.x** | from arduino.cc |
| ESP32 board package by Espressif Systems | installed through Boards Manager (Section 4) |
| USB-serial driver | only if no port appears; use a **data** cable |
| Hardware | see `docs/hardware_inventory.md` |

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

### 3.4 Verify (must all say OK)

```bash
python tools/check_env.py
pytest
```

Expected: ten lines starting with `OK`, then "Environment is ready", then
pytest reporting all tests passed. If a line says `FAIL`, see Section 7.

### 3.5 Lock versions (done once by the team lead, then everyone uses it)

After the whole team's environments work, one person runs:

```bash
pip freeze > requirements.lock.txt
```

and commits it. From then on everyone installs with
`pip install -r requirements.lock.txt` so versions are identical.

---

## 4. Arduino IDE setup (firmware people only)

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

## 5. Folder layout

```
autoshield/
  README.md   requirements.txt   pytest.ini   .gitignore
  contracts/   CAN catalogue, schemas, harness commands, API (Phase 1)
  docs/        hardware_inventory.md, pinmap.md, decisions.md, phase0_roadmap.md
  sim/         simulated vehicle network (Phase 1)
  core/        features, monitors, policy, model, config (Phase 1-2)
  ml/          training code, data/, models/model.json (Phase 2)
  backend/     FastAPI server, hub, serial bridge, storage (Phase 2, 5)
  web/         landing page, dashboard, assets, vendor/ (Phase 3)
  firmware/    gateway/, target/, shared/, tests/, bin/ (Phase 0, 4-7)
  tools/       check_env.py, make_layout.py, later replay/compare/metrics
  tests/       pytest tests
```

Git does not keep empty folders, so each empty folder holds a `.gitkeep` file.
Delete the `.gitkeep` when you add real files to a folder if you like; it is
harmless either way. If a folder ever goes missing, run
`python tools/make_layout.py` (safe to repeat).

---

## 6. Team workflow

- `main` always works. After the Phase 0 first commit, nobody pushes to it
  directly.
- One branch per task: `git checkout -b r2-features` (role + topic).
- Small commits, then open a pull request; another person reviews and merges.
- Pull before you start work: `git pull`.
- Large raw logs go on the shared drive, **not** in Git.
- Contract changes (CAN catalogue, telemetry, API) need a version bump and a
  message to the whole team.

| Role | Owns |
| --- | --- |
| R1 | Firmware and hardware |
| R2 | Data, ML, simulator, monitors, policy |
| R3 | Repository, contracts, backend, integration |
| R4 | Landing page and dashboard |

Fill in names and backups in `docs/decisions.md`.

---

## 7. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `python` not found (Windows) | Reinstall Python and tick **Add python.exe to PATH**, or use `py -3.12` |
| `FAIL` lines in `check_env.py` | venv not activated (no `(.venv)` in prompt), or `pip install` did not finish; activate and reinstall |
| `externally-managed-environment` error | You are installing outside the venv. Activate `.venv` first; do not use `--break-system-packages` |
| `pytest: command not found` | venv not active; use `python -m pytest` |
| Different results on different laptops | Different package versions; use `requirements.lock.txt` |
| Upload fails / port vanishes | Bad cable, or another program (e.g. Serial Monitor) holds the port |
| Two boards, unsure which port is which | Unplug one; the port that disappears is that board. Or run `hello_serial`, which prints the chip model |

---

## 8. Running the system (later)

These do not work until the named phase is merged:

```bash
python -m uvicorn backend.main:app --port 8000     # Phase 2
# landing page:  http://127.0.0.1:8000/            # Phase 3
# dashboard:     http://127.0.0.1:8000/dashboard/  # Phase 3
```

All thresholds in the project are starting values to be tuned from data, not
measured results.
