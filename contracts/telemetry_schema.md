# Telemetry and event schema (contract version 1)

One JSON object per line. Telemetry is sent at 10 Hz; events when something happens.
Lines starting with `#` are debug text and are ignored by the bridge.

## Telemetry message

See `contracts/examples/telemetry.json` (a test parses it).

| Field | Meaning |
| --- | --- |
| type, v | `"telemetry"`, schema version 1 |
| mode | `"sim"` or `"hw"`. The dashboard badge follows this field exactly. |
| t_ms | Time in milliseconds |
| run_id | Id of the recorded run |
| bus | fps (frames per second), load_pct (bus load in percent), rx_overflow (MCP2515 receive overflow count) |
| features | The six features **in this order**: total_rate, dominance, hb_gap_mean_ms, hb_gap_std_ms, imu_gap_mean_ms, imu_gap_std_ms |
| ml | anomaly_score (= minus SVM decision function, higher = more unusual), threshold, anomaly (bool), model (version string) |
| monitors | hb_age_ms, flood (bool), drift_ewma (centi-deg/s), drift_state (`ok`, `warn`, `fault`) |
| nodes | List of: id, state, bank (`A`/`B`), fw (version text), ota_state, isolated (bool) |
| sensor | node, gz_cdps (node value), ref_gz_cdps (reference), trust (0 to 1) |
| context | test_burst (bool), auto_recovery (bool) |
| severity | NORMAL, LOW, MEDIUM, HIGH or CRITICAL |
| action | The action issued in this window, or null |

### Feature definitions

Window = last 1 s of frames, half-open: `t_end - 1 <= t < t_end`, evaluated every 100 ms.

| # | Feature | Definition |
| --- | --- | --- |
| 1 | total_rate | frames in the window / window length (s) |
| 2 | dominance | frames of the most frequent ID / total frames (about 0.70 when healthy) |
| 3 | hb_gap_mean_ms | mean gap between consecutive 0x100 frames |
| 4 | hb_gap_std_ms | standard deviation of those gaps |
| 5 | imu_gap_mean_ms | mean gap between consecutive 0x200 frames |
| 6 | imu_gap_std_ms | standard deviation of those gaps |

If fewer than two frames of an ID are in the window: mean gap = 1000 ms, std = 0.

## Event message

See `contracts/examples/event.json`.

`{"type":"event","v":1,"t_ms":..,"run_id":..,"kind":"..","node":1,"severity":"..","detail":".."}`

Event kinds: `fault_detected`, `severity_change`, `action_taken`, `verify_ok`, `verify_failed`,
`escalate`, `node_isolated`, `node_restored`, `test_burst_started`, `test_burst_ended`,
`sensor_flagged`, `fw_deploy_started`, `canary_started`, `fw_commit`, `fw_rollback`, `mode_change`.

`fault_detected` detail is one of: `canary_unhealthy`, `flood`, `heartbeat_missed`,
`sensor_drift_fault`, `sensor_drift_warn`, `svm_anomaly`.

`action_taken` detail is one of: `soft_reset`, `hard_reset`, `isolate`, `fw_rollback`, `safe_mode`.

## Commands from the laptop to the gateway

```
{"type":"cmd","cmd":"test_burst","node":1,"ms":2000}
{"type":"cmd","cmd":"auto_recovery","on":false}
{"type":"cmd","cmd":"reset_bench"}
{"type":"cmd","cmd":"replay","on":true}
```

Replay lines (replay mode only): `F,<time in microseconds>,<id in hex>,<dlc>,<data bytes in hex>`

## Contract rules

1. Every message carries a version field `v`. Receivers ignore unknown fields and reject an unknown major version.
2. Units: milliseconds for times in telemetry, centi-degrees per second for gyro, milli-g for acceleration, percent for bus load.
3. Anomaly score convention: `anomaly_score = -decision_function`. Higher means more unusual.
4. The `mode` field is `sim` or `hw`.
5. The simulator and the firmware produce the same fields in the same shape.

## Phase 1 decisions (written into the contract so Phase 2 and Phase 5 follow them)

| # | Decision | Why |
| --- | --- | --- |
| 1 | `nodes[].state` is one of BOOT, RUN, CANARY, SAFE, or **MISSING** (the gateway sets MISSING when the heartbeat deadline is exceeded) | A hung node sends nothing, so the gateway cannot read its state |
| 2 | `nodes[].isolated` is true while the relay has cut the node off; while true, a missing heartbeat is expected and is not a fault | Otherwise isolation could never be verified |
| 3 | `context.test_burst` stays true for the burst duration **plus 1 s** (the window length) | Burst frames stay inside the 1 s window after the burst ends |
| 4 | `sensor.trust = clamp(1 - abs(drift_ewma) / fault_limit, 0, 1)` | Defined once, used by simulator, firmware and dashboard |
| 5 | A `fw_deploy_started` event opens a 2 s boot-settling period in which a missing heartbeat is ignored | A node booting a new image is silent for a moment |
| 6 | Informational actions (flag sensor, lower trust, increase monitoring) are never verified or escalated | A sensor flag cannot "fix" drift |
