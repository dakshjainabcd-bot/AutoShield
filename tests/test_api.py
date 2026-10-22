"""API and WebSocket tests (roadmap step 2.8). The simulation runs 50x faster than real time."""
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(speed=50.0, db_path=str(tmp_path / "api.db"), seed=1)
    with TestClient(app) as c:
        yield c


def collect(ws, until, limit=2000):
    """Read messages until until(msg) is true. Returns every message read."""
    seen = []
    for _ in range(limit):
        m = ws.receive_json()
        seen.append(m)
        if until(m):
            return seen
    raise AssertionError("condition never met")


def wait_for_time(ws, t_ms):
    return collect(ws, lambda m: m["type"] == "telemetry" and m["t_ms"] >= t_ms)


def test_health_and_static_pages(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    assert client.get("/dashboard/").status_code == 200
    r = client.get("/api/health")
    assert r.headers["content-type"].startswith("application/json")      # API not shadowed by static files


def test_websocket_delivers_contract_telemetry(client):
    with client.websocket_connect("/ws") as ws:
        msgs = wait_for_time(ws, 2000)
    tel = [m for m in msgs if m["type"] == "telemetry"][-1]
    assert tel["v"] == 1 and tel["mode"] == "sim" and tel["run_id"] >= 1
    assert set(tel) == {"type", "v", "mode", "t_ms", "run_id", "bus", "features", "ml", "monitors",
                        "nodes", "sensor", "context", "severity", "action"}


def test_state_and_events_endpoints(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
    assert client.get("/api/state").json()["type"] == "telemetry"
    assert client.get("/api/events?limit=5").status_code == 200
    assert client.get("/api/events?limit=0").status_code == 422


def test_inject_flood_changes_the_stream_and_the_policy_reacts(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
        r = client.post("/api/inject", json={"fault": "flood", "duration_ms": 3000})
        assert r.status_code == 200 and r.json()["params"]["duration_s"] == 3.0
        msgs = collect(ws, lambda m: m["type"] == "event" and m["kind"] == "verify_ok")
    tel = [m for m in msgs if m["type"] == "telemetry"]
    assert max(t["bus"]["fps"] for t in tel) > 500
    kinds = [(m["kind"], m["detail"]) for m in msgs if m["type"] == "event"]
    assert ("fault_detected", "flood") in kinds and ("action_taken", "isolate") in kinds


def test_inject_validation(client):
    assert client.post("/api/inject", json={"fault": "meteor"}).status_code == 422
    assert client.post("/api/inject", json={"fault": "flood", "duration_ms": 0}).status_code == 422
    assert client.post("/api/inject", json={"fault": "flood", "duration_ms": 999999}).status_code == 422


def test_control_commands(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
        assert client.post("/api/control", json={"cmd": "auto_recovery"}).status_code == 422
        assert client.post("/api/control", json={"cmd": "auto_recovery", "on": False}).status_code == 200
        msgs = collect(ws, lambda m: m["type"] == "telemetry" and m["context"]["auto_recovery"] is False)
        assert client.post("/api/control", json={"cmd": "test_burst", "ms": 1000}).status_code == 200
        collect(ws, lambda m: m["type"] == "event" and m["kind"] == "test_burst_started")
        assert client.post("/api/control", json={"cmd": "reset_bench"}).status_code == 200
        assert client.post("/api/control", json={"cmd": "dance"}).status_code == 422


def test_faulty_firmware_inject_then_conflict_when_hung(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
        client.post("/api/control", json={"cmd": "auto_recovery", "on": False})
        assert client.post("/api/inject", json={"fault": "hang"}).status_code == 200
        collect(ws, lambda m: m["type"] == "telemetry" and m["nodes"][0]["state"] == "MISSING")
        assert client.post("/api/inject", json={"fault": "faulty_fw"}).status_code == 409


def test_runs_start_stop_and_csv_export(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
        rid = client.post("/api/runs/start", json={"label": "my run"}).json()["run_id"]
        collect(ws, lambda m: m["type"] == "telemetry" and m["run_id"] == rid)
        client.post("/api/inject", json={"fault": "flood", "duration_ms": 2000})
        collect(ws, lambda m: m["type"] == "event" and m["kind"] == "fault_detected")
        stopped = client.post("/api/runs/stop").json()["stopped_run_id"]
    assert stopped == rid
    runs = client.get("/api/runs").json()
    mine = [r for r in runs if r["id"] == rid][0]
    assert mine["label"] == "my run" and mine["n_telemetry"] > 0 and mine["end_utc"]
    r = client.get(f"/api/export.csv?run_id={rid}")
    assert r.status_code == 200 and r.text.startswith("t_ms,severity")
    assert client.get(f"/api/export.csv?run_id={rid}&what=events").text.startswith("t_ms,kind")
    assert client.get("/api/export.csv?run_id=9999").status_code == 404
    assert client.get("/api/export.csv").status_code == 422


def test_stopped_run_records_nothing_more(client):
    with client.websocket_connect("/ws") as ws:
        wait_for_time(ws, 1500)
        rid = client.post("/api/runs/start", json={"label": "short"}).json()["run_id"]
        collect(ws, lambda m: m["type"] == "telemetry" and m["run_id"] == rid)
        client.post("/api/runs/stop")
        msgs = collect(ws, lambda m: m["type"] == "telemetry" and m["run_id"] == 0)
        assert msgs[-1]["run_id"] == 0
    n1 = [r for r in client.get("/api/runs").json() if r["id"] == rid][0]["n_telemetry"]
    time.sleep(0.3)
    n2 = [r for r in client.get("/api/runs").json() if r["id"] == rid][0]["n_telemetry"]
    assert n1 == n2


def test_missing_model_file_runs_without_svm(tmp_path):
    app = create_app(speed=50.0, db_path=str(tmp_path / "x.db"), model_path=tmp_path / "nope.json")
    with TestClient(app) as c, c.websocket_connect("/ws") as ws:
        m = wait_for_time(ws, 1500)[-1]
    assert m["ml"]["model"] == "none" and m["ml"]["anomaly"] is False
