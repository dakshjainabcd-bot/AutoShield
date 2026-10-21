# Decisions, roles and dates (Phase 0, step 0.7)

## Roles

| Role | Name | Backup |
| --- | --- | --- |
| R1 Firmware and hardware | | |
| R2 Data and ML | | |
| R3 Backend and integration | | |
| R4 Frontend | | |

## Dates

| Milestone | Date |
| --- | --- |
| EL Review 2 | |
| EL Review 3 | |

## Key decisions D1 to D10 (roadmap Section 1.3)

Each member writes AGREE, or OBJECT with a reason.

| # | Decision | Member 1 | Member 2 | Member 3 | Member 4 |
| --- | --- | --- | --- | --- | --- |
| D1 | Simulation first, hardware integration late | | | | |
| D2 | Python reference first, then C++ port with parity tests | | | | |
| D3 | Arduino IDE 2.x with the Espressif ESP32 package | | | | |
| D4 | Gateway telemetry over USB serial as JSON lines | | | | |
| D5 | Custom HTML/CSS/JS served by FastAPI (no Streamlit) | | | | |
| D6 | Faults injected via the target's own USB serial | | | | |
| D7 | Canary firmware over Wi-Fi HTTP (HTTPUpdate) | | | | |
| D8 | Isolation by relay on the MCP2515 module supply; reset via EN pin | | | | |
| D9 | SQLite for storage | | | | |
| D10 | Timestamps taken by the ESP32 on receive | | | | |
