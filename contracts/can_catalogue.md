# CAN catalogue (contract version 1)

Classic CAN, 11-bit IDs, 500 kbit/s. A lower ID has higher priority in arbitration.
Multi-byte numbers are **little-endian** (least significant byte first).
Every frame in this catalogue has 8 data bytes (DLC 8), so a healthy bus carries
about **71 frames per second**: 10 (0x020) + 10 (0x100) + 1 (0x110) + 50 (0x200).

| ID | Name | Sender | Period | Payload (byte index) |
| --- | --- | --- | --- | --- |
| 0x010 | SUP_CMD | Gateway | On event | [0] target node (0xFF = all), [1] command code, [2..3] argument (uint16), [4..7] zero |
| 0x020 | SUP_HB | Gateway | 100 ms | [0] rolling counter, [1] gateway mode (0 monitor, 1 alert, 2 safe), [2..7] zero |
| 0x050 | (spam, faults only) | Faulty node | Fault only | Not part of healthy traffic. Used for flood injection. Its low ID wins arbitration. |
| 0x100 | NODE1_HB | Target node 1 | 100 ms | [0] node id (1), [1] rolling counter, [2] state code, [3] bank (0 first slot, 1 second slot), [4..7] uptime in ms (uint32) |
| 0x110 | NODE1_FWINFO | Target node 1 | 1 s and at boot | [0] major, [1] minor, [2] patch, [3] OTA state code, [4..5] build id (uint16), [6..7] zero |
| 0x1F0 | TEST_BURST | Target node 1 | During a test burst only | Any payload. Sent at a high rate when the gateway commands TEST_BURST. |
| 0x200 | NODE1_IMU | Target node 1 | 20 ms | [0..1] gyro_z in centi-degrees per second (int16), [2..3] ax in milli-g (int16), [4..5] ay in milli-g (int16), [6..7] az in milli-g (int16) |

The IMU's default full-scale range of 250 deg/s is 25000 in centi-deg/s and 2 g is
2000 in milli-g. Both fit in a signed 16-bit integer.

## Supervisor command codes (byte 1 of 0x010)

| Code | Name | Meaning |
| --- | --- | --- |
| 0x01 | SOFT_RESET | Node restarts itself |
| 0x02 | SILENCE | Node stops sending application frames (software isolation) |
| 0x03 | RESUME | Node resumes sending |
| 0x04 | FW_COMMIT | Node calls esp_ota_mark_app_valid_cancel_rollback() |
| 0x05 | FW_ROLLBACK | Node calls esp_ota_mark_app_invalid_rollback_and_reboot() |
| 0x06 | TEST_BURST | Node sends 0x1F0 frames at a high rate for the duration in ms in bytes [2..3] (uint16) |
| 0x07 | SAFE_MODE | Node sends only its heartbeat and reports state SAFE |

Two actions are **not** CAN commands: the **hard reset** (gateway pulls the target's EN pin low)
and **isolation** (a relay cuts power to the target's MCP2515 module). They work even if the
node ignores commands.

## Code tables

| Field | Values |
| --- | --- |
| Node state (0x100 byte 2) | 0 BOOT, 1 RUN, 2 CANARY, 3 SAFE |
| OTA state (0x110 byte 3) | 0 unknown, 1 new, 2 pending verify, 3 valid, 4 invalid or aborted |
| Severity | NORMAL, LOW, MEDIUM, HIGH, CRITICAL |
| Gateway mode | 0 monitor only (auto-recovery off), 1 alert, 2 safe |

## Rate limits used by the per-ID rate monitor

| ID | Expected rate | Flood limit |
| --- | --- | --- |
| 0x020, 0x100 | 10 per s | more than 30 per s |
| 0x110 | 1 per s | more than 3 per s |
| 0x200 | 50 per s | more than 150 per s |
| every other ID (0x010, 0x050, 0x1F0, unknown) | none | more than 20 per s |

An ID must be over its limit in 3 windows in a row. 0x1F0 is ignored while a
gateway-started test burst is active.

## Phase 1 notes (clarifications that do not change any frame)

* The names SILENT and HUNG exist **only inside the simulator**. They are never on the wire.
* Frames are timestamped by the ESP32 when it reads them (decision D10). The MCP2515 has no message timestamp.
