import csv
import io

from backend.gateway import VirtualGateway
from backend.store import Store


def make(tmp_path):
    return Store(tmp_path / "t.db")


def fill(gw, store, n=30):
    for _ in range(n):
        tel, evs = gw.step()
        store.add_telemetry(tel)
        for e in evs:
            store.add_event(e)


def test_run_lifecycle_and_counts(tmp_path):
    s = make(tmp_path)
    assert s.current_run_id == 0
    rid = s.start_run("demo", "sim", "1.0", {"a": 1})
    gw = VirtualGateway(seed=1, run_id=rid)
    fill(gw, s)
    gw.apply("flood", duration_s=2.0)
    fill(gw, s, 30)
    runs = s.list_runs()
    assert len(runs) == 1 and runs[0]["label"] == "demo" and runs[0]["n_telemetry"] == 60
    assert runs[0]["n_events"] > 0 and runs[0]["end_utc"] is None
    assert s.stop_run() == rid
    assert s.list_runs()[0]["end_utc"] is not None
    s.close()


def test_run_id_zero_is_not_recorded(tmp_path):
    s = make(tmp_path)
    s.start_run("x", "sim", "1.0")
    fill(VirtualGateway(seed=1, run_id=0), s, 10)
    assert s.list_runs()[0]["n_telemetry"] == 0
    s.close()


def test_starting_a_new_run_closes_the_old_one(tmp_path):
    s = make(tmp_path)
    a = s.start_run("a", "sim", "1.0")
    b = s.start_run("b", "sim", "1.0")
    runs = {r["id"]: r for r in s.list_runs()}
    assert a != b and runs[a]["end_utc"] is not None and runs[b]["end_utc"] is None
    s.close()


def test_csv_export_telemetry_and_events(tmp_path):
    s = make(tmp_path)
    rid = s.start_run("csv", "sim", "1.0")
    gw = VirtualGateway(seed=1, run_id=rid)
    fill(gw, s, 20)
    gw.apply("flood", duration_s=2.0)
    fill(gw, s, 30)
    rows = list(csv.reader(io.StringIO(s.export_csv(rid))))
    assert rows[0][0] == "t_ms" and len(rows) == 1 + 50
    assert "fps" in rows[0] and "severity" in rows[0]
    ev_rows = list(csv.reader(io.StringIO(s.export_csv(rid, "events"))))
    assert ev_rows[0] == ["t_ms", "kind", "severity", "node", "detail"]
    assert any(r[1] == "fault_detected" for r in ev_rows[1:])
    s.close()


def test_data_survives_reopening_the_file(tmp_path):
    s = make(tmp_path)
    rid = s.start_run("keep", "sim", "1.0")
    fill(VirtualGateway(seed=1, run_id=rid), s, 15)
    s.close()
    s2 = make(tmp_path)
    assert len(s2.telemetry(rid)) == 15
    s2.close()
