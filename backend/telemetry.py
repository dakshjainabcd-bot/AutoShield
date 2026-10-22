"""Build the telemetry message of contracts/telemetry_schema.md from a StepResult."""
from core import catalogue as C
from core import can_codec as codec


class NodeTracker:
    """What the gateway has LEARNED about the node by reading frames (never from the
    simulator's internals): state and bank from 0x100, version and OTA state from
    0x110, the latest gyro value from 0x200."""

    def __init__(self):
        self.state = "BOOT"
        self.bank = "A"
        self.fw = "0.0.0"
        self.ota_state = "UNKNOWN"
        self.gz_cdps = 0

    def observe_frames(self, frames):
        for f in sorted(frames, key=lambda fr: fr[0]):
            if not f.data:
                continue
            if f.can_id == C.ID_NODE_HB:
                d = codec.decode_hb(f.data)
                self.state = C.NODE_STATE_NAMES.get(d["state_code"], "UNKNOWN")
                self.bank = "A" if d["bank"] == 0 else "B"
            elif f.can_id == C.ID_NODE_FWINFO:
                d = codec.decode_fwinfo(f.data)
                self.fw = "{}.{}.{}".format(*d["version"])
                self.ota_state = C.OTA_STATE_NAMES.get(d["ota_code"], "UNKNOWN")
            elif f.can_id == C.ID_NODE_IMU:
                self.gz_cdps = codec.decode_imu(f.data)["gz_cdps"]


def build_telemetry(res, *, mode, run_id, model_version, threshold, tracker, ref_gz,
                    auto_recovery, hb_deadline_ms, node_id=1):
    """res is a core.supervisor.StepResult."""
    state = tracker.state
    if res.hb_age_ms > hb_deadline_ms:
        state = "MISSING"          # contract: the gateway reports MISSING when the heartbeat is overdue
    return {
        "type": "telemetry", "v": 1, "mode": mode,
        "t_ms": int(round(res.t * 1000)), "run_id": run_id,
        "bus": {"fps": round(res.fps, 1), "load_pct": round(res.load_pct, 2), "rx_overflow": 0},
        "features": [round(x, 3) for x in res.features],
        "ml": {"anomaly_score": round(res.anomaly_score, 4), "threshold": threshold,
               "anomaly": bool(res.anomaly_raw), "model": model_version},
        "monitors": {"hb_age_ms": int(round(res.hb_age_ms)), "flood": bool(res.flags.flood),
                     "drift_ewma": round(res.drift_ewma, 2), "drift_state": res.flags.drift},
        "nodes": [{"id": node_id, "state": state, "bank": tracker.bank, "fw": tracker.fw,
                   "ota_state": tracker.ota_state, "isolated": bool(res.context.isolated)}],
        "sensor": {"node": node_id, "gz_cdps": int(tracker.gz_cdps),
                   "ref_gz_cdps": int(round(ref_gz)), "trust": round(res.drift_trust, 3)},
        "context": {"test_burst": bool(res.context.test_burst),
                    "auto_recovery": bool(auto_recovery)},
        "severity": res.decision.severity,
        "action": res.decision.action,
    }
