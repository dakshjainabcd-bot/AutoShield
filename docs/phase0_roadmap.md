# AutoShield, Phase 0: Foundations and Environment

A step-by-step guide for the person doing Phase 0. Beginner friendly: follow the
steps in order, tick the boxes, and do not skip the checks.

- **Goal:** everyone can run the same code, the hardware has been inspected, each
  board prints a message, and the repository is ready for the team.
- **Effort:** 3 to 5 days. **Depends on:** nothing. **Deferrable:** no.
- **Why it matters:** most beginner delays come from laptops that differ, bad USB
  cables and hardware surprises. Finding them now costs hours; in Phase 5 it costs days.

## What was tested, and what was not

| Tested by running it (Linux, Python 3.12.3) | Not tested (do these on your machine) |
| --- | --- |
| `requirements.txt` installs in a fresh venv; `tools/check_env.py` prints OK for all ten packages; `pytest` passes; `tools/make_layout.py` creates the layout and is safe to repeat | Windows and macOS commands, Arduino IDE steps, both `.ino` sketches (not compiled), your exact boards, drivers |

Anything in the right-hand column is marked **Check on your machine**. Record what you saw.

## Corrections and gaps found in the roadmap while preparing this

| # | Issue in the original | What this guide does |
| --- | --- | --- |
| 1 | `pytest` cannot import `core`, `sim`, `backend` from `tests/` unless the project root is on the path | Added `pytest.ini` (`pythonpath = .`) and empty `__init__.py` files in `sim`, `core`, `ml`, `backend` |
| 2 | Windows PowerShell blocks `.venv\Scripts\Activate.ps1` by default | README gives the one-line fix, or use Command Prompt |
| 3 | GitHub rejects account passwords for HTTPS pushes | README says to use GitHub Desktop, `gh auth login` or a token |
| 4 | "Nobody pushes directly to main" conflicts with the very first commit | First commit to `main` is allowed in Phase 0; the rule applies afterwards |
| 5 | `.gitignore` list mentions "Arduino build output" but `firmware/bin/` must stay tracked for Phase 7 images | `.gitignore` ignores `build/`, `*.elf`, `*.map` only, never `firmware/bin/` |
| 6 | Pin list omits GPIO19/20 (native USB on the S3) | Added to `docs/pinmap.md`, marked Check on your machine |
| 7 | Contents page lists "5. Interface contracts" etc. after the phases, while phases come after Section 4 | Cosmetic; no action |
| 8 | The roadmap's tested package versions (for example numpy 2.4.4) differ from today's installs (numpy 2.5.4, scikit-learn 1.9.1, pandas 3.0.6, fastapi 0.156.8 in my test) | Do not pin by hand; freeze `requirements.lock.txt` once the team's setups work |

## Prerequisites checklist

**Software:** Git, a GitHub account, Python 3.12 (with pip and venv), VS Code (optional),
Arduino IDE 2.x, a USB-serial driver only if needed, Chrome/Edge/Firefox.
**Hardware:** both ESP32 boards, **data** USB cables, the Bill of Materials.
**Laptop:** two free USB ports (or a powered hub).

## Step A: Install the tools

| Tool | Windows | macOS | Linux (Ubuntu/Debian) |
| --- | --- | --- | --- |
| Git | git-scm.com installer, keep defaults | `xcode-select --install` | `sudo apt install git` |
| Python 3.12 | python.org installer, **tick "Add python.exe to PATH"** | python.org installer | `sudo apt install python3 python3-venv python3-pip` |
| Arduino IDE 2.x | arduino.cc installer | arduino.cc | arduino.cc (AppImage or zip) |

Verify (new terminal): `git --version` and `python --version` (`python3 --version` on
macOS/Linux). Expect Python 3.12.x. If another recent version is installed, it may work;
if `pip install` fails, install 3.12.

## Step B: Git identity and GitHub login

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Sign in with GitHub Desktop, `gh auth login`, or a Personal Access Token when Git asks
for a password.

## Step C (0.1): Get the repository and add the Phase 0 files

1. On GitHub, make sure the repo `autoshield` exists and every teammate is a collaborator
   (Settings, Collaborators).
2. Clone and enter it:
   ```bash
   git clone <REPOSITORY URL>
   cd autoshield
   ```
3. Unzip `autoshield_phase0.zip` and copy **everything inside** its `autoshield` folder into
   your clone (overwrite the existing one-line `README.md`). Make sure hidden files such as
   `.gitignore` came across.
4. Make sure the layout is complete (safe to repeat):
   ```bash
   python tools/make_layout.py
   ```
   Windows without `python` on PATH: `py tools\make_layout.py`.

## Step D (0.2): Python environment

Run from the repository root.

```bash
# create (once)       Windows: python -m venv .venv      macOS/Linux: python3 -m venv .venv
# activate (each terminal):
#   Windows cmd:        .venv\Scripts\activate.bat
#   Windows PowerShell: .venv\Scripts\Activate.ps1
#   macOS/Linux:        source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python tools/check_env.py
pytest
```

**Pass:** ten `OK` lines, "Environment is ready", all tests passed. Paste your output in the
team chat. If versions differ between laptops, that is fine for now; Step L fixes it.

## Step E (0.3): Arduino IDE

1. Open **File, Preferences** (macOS: **Arduino IDE, Settings**). In *Additional boards
   manager URLs* paste `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
2. **Tools, Board, Boards Manager**, search `esp32`, install **esp32 by Espressif Systems**.
3. Write the version number in `docs/hardware_inventory.md`.
4. Board choice: classic ESP32 = **ESP32 Dev Module**; S3 = **ESP32S3 Dev Module**.

**Check on your machine:** menu names can shift slightly between IDE versions.

## Step F (0.4): Inspect the hardware

Photograph everything, then fill `docs/hardware_inventory.md`.

- [ ] Count every item against the order; note missing or broken parts.
- [ ] **S3 module marking** (for example N8R2, N16R8): the number after N is flash (MB),
      after R is PSRAM (MB). Never use GPIO35 to 37, whichever variant you have.
- [ ] **MCP2515 crystal:** read the number on top of the silver crystal (8.000 or 16.000 MHz).
      Code later needs `MCP_8MHZ` or `MCP_16MHZ`; a mismatch means no communication.
- [ ] Pin headers soldered on every board and module? If not, plan the soldering.
- [ ] Cables: they pass the data-cable test in Step G.
- [ ] The ESP32-S3-DevKitC-1 has two USB connectors (USB-to-UART and native USB). Use the
      **USB-to-UART** port by default. If you use the native port, set
      **Tools, USB CDC On Boot: Enabled**.

## Step G (0.5): First upload on both boards

1. Plug in one board. Choose its board and port (**Tools, Port**).
2. Open `firmware/tests/hello_serial/hello_serial.ino`, click **Upload**.
3. Open **Serial Monitor**, set **115200 baud**. Expect one line per second including the
   chip model, which tells you which board is on that port.
4. Upload will not start: hold **BOOT**, tap and release **RESET**, release **BOOT**, retry.
5. No port appears: try another cable first (usually charge-only), then install the driver
   for the USB-to-serial chip printed on the board.
6. Repeat for the second board. Then plug both in and confirm **two different ports**.
   Write down which is which (Windows COM numbers can change when you use another socket).
7. Close the Serial Monitor before uploading again; only one program can hold a port.

Linux: `sudo usermod -a -G dialout $USER`, then log out and in.

## Step H: Read chip details and default pins

Open `firmware/tests/board_info/board_info.ino`, upload it to **each** board with its own
board type selected, open Serial Monitor at 115200. It prints chip model, flash size, PSRAM,
free heap and the default SPI (SS, MOSI, MISO, SCK) and I2C (SDA, SCL) pins. Copy them into
`docs/hardware_inventory.md` and `docs/pinmap.md`.

**Check on your machine:** PSRAM reads 0 unless it is enabled under **Tools, PSRAM**; that
is not a fault. Compile-check both sketches now; I could not.

## Step I (0.6): Learning sprint and glossary

For your own role, work through the topics in roadmap Section 2.1 using official docs, and
pass each "You are ready when you can..." test. Keep a shared glossary (ECU, CAN, ID,
arbitration, heartbeat, DLC, termination, SPI, I2C, RTOS, OTA, nu, gamma, support vector).

## Step J (0.7): Confirm decisions, roles, dates (1 hour, whole team)

Fill `docs/decisions.md`: each member writes AGREE or OBJECT for D1 to D10, roles R1 to R4
with a backup each, and the EL Review 2 and 3 dates.

## Step K: Commit and push the first commit

```bash
git status
git add .
git commit -m "Phase 0: repository layout, environment, README, test sketches"
git push origin main
```

(First commit straight to `main` is allowed in Phase 0 only.) If `git push` asks to sign in,
see Step B. Afterwards work on branches: `git checkout -b phase0-notes`.

## Step L: Teammates onboard, then freeze versions

1. Send the message below.
2. Each teammate follows the README (Sections 2 and 3) and pastes their `check_env.py` output.
3. When all pass, one person runs `pip freeze > requirements.lock.txt`, commits and pushes it.
   Everyone then uses `pip install -r requirements.lock.txt`.
4. Tag the finish: `git tag phase0-done` then `git push origin phase0-done`.

> Hi team, Phase 0 is on `main`. Please `git clone` (or `git pull`), then follow README
> Sections 2 and 3 and paste the output of `python tools/check_env.py` and `pytest` here.
> Firmware folks also do Section 4. All of you read your role's phases in the roadmap.

## Deliverables

- Repository with the agreed layout, `.gitignore`, `requirements.txt`, `pytest.ini`, README
- Working Python environment on every laptop
- Arduino IDE with the ESP32 package, version recorded
- Inspection photos and `docs/hardware_inventory.md`
- Crystal frequency, S3 variant, and which port is which, written down
- `docs/pinmap.md` with the forbidden pins

## Phase 0 checklist (definition of done)

- [ ] Everyone has cloned the repository and can pull and push.
- [ ] `python tools/check_env.py` prints OK for every package on every laptop.
- [ ] Both ESP32 boards print a message in the Serial Monitor.
- [ ] The two boards appear as two different ports at the same time.
- [ ] The crystal frequency of each MCP2515 module is written down.
- [ ] The S3 variant is written down; forbidden pins are on the team pin sheet.
- [ ] Pin headers are soldered, or a soldering plan exists.
- [ ] Roles, backups and dates are filled in.
- [ ] `requirements.lock.txt` is committed; `phase0-done` is tagged.

## Common problems

| Problem | Fix |
| --- | --- |
| `python` not found (Windows) | Reinstall with PATH ticked, or use `py -3.12` |
| `FAIL` in check_env | venv not active, or install incomplete |
| `externally-managed-environment` | You are outside the venv; activate it |
| Upload fails or port disappears | Bad cable, or another program holds the port |
| Different results on different laptops | Use `requirements.lock.txt` |
| `pytest` cannot import `core` | Run from the repo root; `pytest.ini` must be present |
