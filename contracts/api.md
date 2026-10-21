# Backend API (contract version 1)

The browser talks to the backend only through these endpoints. The WebSocket carries data
from the server to the browser; commands go the other way through REST.

| Method | Path | Purpose and body | Phase |
| --- | --- | --- | --- |
| GET | /api/health | Returns `{"status":"ok"}` | 2 |
| GET | /api/state | Latest telemetry message | 2 |
| GET | /api/events?limit=100 | Recent events | 2 |
| POST | /api/inject | `{"fault":"flood" or "hang" or "drift" or "faulty_fw", "duration_ms":..., "slope":...}`. In simulation it drives the simulator; in hardware mode it forwards to the target's serial | 2, 6 |
| POST | /api/control | `{"cmd":"auto_recovery" or "reset_bench" or "test_burst", ...}` | 2, 6 |
| POST | /api/mode | `{"source":"sim" or "hw", "gateway_port":..., "target_port":...}` | 5 |
| GET | /api/ports | List of serial ports found | 5 |
| POST | /api/firmware/deploy | `{"image":"good" or "faulty" or "crashing"}` | 7 |
| GET | /api/runs | List of recorded experiment runs | 2 |
| POST | /api/runs/start, /api/runs/stop | Start and stop recording a labelled run | 2 |
| GET | /api/metrics | Aggregated metrics per fault | 8 |
| GET | /api/export.csv?run_id=... | CSV export of a run | 2 |
| WS | /ws | Server to browser stream of telemetry and event messages | 2 |

Note: `/api/inject` takes `duration_ms` (milliseconds, like every time in the contract); the
Python simulator method takes `duration_s` (seconds). The backend converts.
