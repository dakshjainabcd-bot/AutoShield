"""SQLite storage (roadmap step 2.8). Python's built-in sqlite3, no server needed.

Tables
  runs       id, start_utc, end_utc, mode, label, model_version, git_commit, config_json
  telemetry  id, t_ms, run_id, json
  events     id, t_ms, run_id, kind, node, detail, json

run_id 0 means "not recording": such messages are not stored.
Writes are buffered and written in batches by flush() (about once per second),
so the database never slows the 10 Hz stream.
"""
import csv
import io
import json
import sqlite3
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, start_utc TEXT NOT NULL, end_utc TEXT,
  mode TEXT, label TEXT, model_version TEXT, git_commit TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS telemetry(
  id INTEGER PRIMARY KEY AUTOINCREMENT, t_ms INTEGER, run_id INTEGER, json TEXT);
CREATE INDEX IF NOT EXISTS ix_tel_run ON telemetry(run_id, t_ms);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, t_ms INTEGER, run_id INTEGER,
  kind TEXT, node INTEGER, detail TEXT, json TEXT);
CREATE INDEX IF NOT EXISTS ix_ev_run ON events(run_id, t_ms);
"""

TELEMETRY_COLUMNS = ["t_ms", "severity", "action", "fps", "load_pct", "rx_overflow",
                     "anomaly_score", "anomaly", "hb_age_ms", "flood", "drift_ewma",
                     "drift_state", "node_state", "bank", "gz_cdps", "ref_gz_cdps", "trust",
                     "test_burst", "auto_recovery"]
EVENT_COLUMNS = ["t_ms", "kind", "severity", "node", "detail"]


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit():
    try:
        root = Path(__file__).resolve().parent.parent
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=2)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class Store:
    def __init__(self, path):
        self._db_lock = threading.Lock()
        self._buf_lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._tel, self._ev = [], []
        self.current_run_id = 0
        self._git = _git_commit()

    # ----- runs --------------------------------------------------------------
    def start_run(self, label, mode, model_version, config=None):
        """Ends the open run (if any) and starts a new one. Returns the new run id."""
        self.flush()
        with self._db_lock:
            if self.current_run_id:
                self._conn.execute("UPDATE runs SET end_utc=? WHERE id=?",
                                   (_utc_now(), self.current_run_id))
            cur = self._conn.execute(
                "INSERT INTO runs(start_utc, mode, label, model_version, git_commit, config_json) "
                "VALUES(?,?,?,?,?,?)",
                (_utc_now(), mode, label, model_version, self._git, json.dumps(config or {})))
            self._conn.commit()
            self.current_run_id = cur.lastrowid
            return self.current_run_id

    def stop_run(self):
        """Ends the open run. Returns its id, or None if nothing was recording."""
        self.flush()
        with self._db_lock:
            rid = self.current_run_id
            if rid:
                self._conn.execute("UPDATE runs SET end_utc=? WHERE id=?", (_utc_now(), rid))
                self._conn.commit()
            self.current_run_id = 0
            return rid or None

    def list_runs(self):
        self.flush()
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT r.id, r.start_utc, r.end_utc, r.mode, r.label, r.model_version, "
                "r.git_commit, (SELECT COUNT(*) FROM telemetry t WHERE t.run_id=r.id) "
                "AS n_telemetry, (SELECT COUNT(*) FROM events e WHERE e.run_id=r.id) AS n_events "
                "FROM runs r ORDER BY r.id").fetchall()
            return [dict(r) for r in rows]

    def run_exists(self, run_id):
        with self._db_lock:
            return self._conn.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is not None

    # ----- writing -----------------------------------------------------------
    def add_telemetry(self, msg):
        if not msg.get("run_id"):
            return
        with self._buf_lock:
            self._tel.append((msg["t_ms"], msg["run_id"], json.dumps(msg)))

    def add_event(self, ev):
        if not ev.get("run_id"):
            return
        with self._buf_lock:
            self._ev.append((ev["t_ms"], ev["run_id"], ev["kind"], ev.get("node"),
                             ev.get("detail"), json.dumps(ev)))

    def flush(self):
        with self._buf_lock:
            tel, ev = self._tel, self._ev
            self._tel, self._ev = [], []
        if not tel and not ev:
            return
        with self._db_lock:
            self._conn.executemany("INSERT INTO telemetry(t_ms, run_id, json) VALUES(?,?,?)", tel)
            self._conn.executemany(
                "INSERT INTO events(t_ms, run_id, kind, node, detail, json) VALUES(?,?,?,?,?,?)", ev)
            self._conn.commit()

    # ----- reading and export -----------------------------------------------
    def telemetry(self, run_id):
        self.flush()
        with self._db_lock:
            rows = self._conn.execute("SELECT json FROM telemetry WHERE run_id=? ORDER BY id",
                                      (run_id,)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def events(self, run_id):
        self.flush()
        with self._db_lock:
            rows = self._conn.execute("SELECT json FROM events WHERE run_id=? ORDER BY id",
                                      (run_id,)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def export_csv(self, run_id, what="telemetry"):
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        if what == "events":
            w.writerow(EVENT_COLUMNS)
            for e in self.events(run_id):
                w.writerow([e["t_ms"], e["kind"], e["severity"], e["node"], e["detail"]])
        else:
            w.writerow(TELEMETRY_COLUMNS)
            for m in self.telemetry(run_id):
                node = m["nodes"][0]
                w.writerow([m["t_ms"], m["severity"], m["action"] or "", m["bus"]["fps"],
                            m["bus"]["load_pct"], m["bus"]["rx_overflow"],
                            m["ml"]["anomaly_score"], m["ml"]["anomaly"],
                            m["monitors"]["hb_age_ms"], m["monitors"]["flood"],
                            m["monitors"]["drift_ewma"], m["monitors"]["drift_state"],
                            node["state"], node["bank"], m["sensor"]["gz_cdps"],
                            m["sensor"]["ref_gz_cdps"], m["sensor"]["trust"],
                            m["context"]["test_burst"], m["context"]["auto_recovery"]])
        return out.getvalue()

    def close(self):
        self.flush()
        with self._db_lock:
            self._conn.close()
