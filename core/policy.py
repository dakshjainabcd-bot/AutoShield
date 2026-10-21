"""Context and severity policy (roadmap step 1.8) with verify and escalate.

classify() is the policy TABLE (first match wins). PolicyEngine wraps it with
the verify loop, escalation, cooldown and isolation restore.

Design decisions made in Phase 1 (they close gaps in the original text):
  * Corrective actions (RESTART, ISOLATE, FW_ROLLBACK, SAFE_MODE) are verified
    and can escalate. Informational actions (FLAG_SENSOR, LOWER_TRUST,
    INCREASE_MONITORING) are NOT verified: a sensor flag cannot "fix" drift.
  * While a node is isolated its silence is expected, so 'heartbeat missed'
    is ignored (otherwise isolation could never be verified).
  * After an isolation is verified the node is held isolated for
    isolation_hold_s, then restored (relay back + hard reset).
"""
from dataclasses import dataclass, field, replace
from typing import List, Optional

from core import catalogue as C
from core.config import load_config

CORRECTIVE = {"RESTART", "ISOLATE", "FW_ROLLBACK", "SAFE_MODE"}

# Human-readable reason for each policy-table row (used in fault_detected events).
ROW_REASON = {1: "canary_unhealthy", 2: "flood", 3: "heartbeat_missed",
              4: "sensor_drift_fault", 5: "sensor_drift_warn", 6: "svm_anomaly"}


def make_event(t, kind, severity, detail, run_id=0, node=1):
    """Build an event message exactly as in contracts/telemetry_schema.md."""
    return {"type": "event", "v": 1, "t_ms": int(round(t * 1000)), "run_id": run_id,
            "kind": kind, "node": node, "severity": severity, "detail": detail}


@dataclass(frozen=True)
class Flags:
    anomaly: bool = False      # SVM anomaly (always False until Phase 2)
    hb_missed: bool = False
    flood: bool = False
    drift: str = "ok"          # 'ok' | 'warn' | 'fault'


@dataclass(frozen=True)
class Context:
    test_burst: bool = False   # a gateway-started test burst is active
    node_state: str = "RUN"    # as OBSERVED from the node's heartbeat
    isolated: bool = False     # the gateway has isolated the node


@dataclass
class Decision:
    severity: str = "NORMAL"
    action: Optional[str] = None   # action issued in THIS step, else None
    events: List[dict] = field(default_factory=list)
    state: str = "MONITORING"
    row: int = 8                   # policy table row that matched (for tests)


def classify(flags, ctx, anomaly_streak=0, anomaly_medium_windows=50, anomaly_low_windows=3):
    """The policy table. Returns (severity, action_family, row_number)."""
    if ctx.node_state == "CANARY" and (flags.anomaly or flags.hb_missed or flags.flood):
        return "CRITICAL", "FW_ROLLBACK", 1
    if flags.flood and not ctx.test_burst:
        return "HIGH", "ISOLATE", 2
    if flags.hb_missed:
        return "MEDIUM", "RESTART", 3
    if flags.drift == "fault":
        return "MEDIUM", "FLAG_SENSOR", 4
    if flags.drift == "warn":
        return "LOW", "LOWER_TRUST", 5
    if flags.anomaly and anomaly_streak >= anomaly_low_windows and not ctx.test_burst:
        if anomaly_streak >= anomaly_medium_windows:
            return "MEDIUM", "RESTART", 6
        return "LOW", "INCREASE_MONITORING", 6
    if ctx.test_burst:
        return "NORMAL", None, 7
    return "NORMAL", None, 8


_ESCALATION = {"RESTART": "ISOLATE", "ISOLATE": "SAFE_MODE", "FW_ROLLBACK": "SAFE_MODE"}
_SEVERITY_OF = {"RESTART": "MEDIUM", "ISOLATE": "HIGH", "FW_ROLLBACK": "CRITICAL",
                "SAFE_MODE": "CRITICAL"}


class PolicyEngine:
    """Call step() once per 100 ms window. States:
    MONITORING -> VERIFYING -> COOLDOWN -> MONITORING, with ISOLATED_HOLD after a
    verified isolation and LATCHED when even the last escalation failed.
    """

    def __init__(self, cfg=None, run_id=0, node_id=1, auto_recovery=True):
        self.cfg = cfg or load_config()
        self.p = self.cfg["policy"]
        self.step_s = self.cfg["step_s"]
        self.run_id = run_id
        self.node_id = node_id
        self.auto_recovery = auto_recovery
        self.reset()

    def reset(self):
        self.state = "MONITORING"
        self.last_sev = "NORMAL"
        self.anomaly_streak = 0
        self.family = None
        self.phase = None
        self.t_action = 0.0
        self.t_deadline = 0.0
        self.healthy_streak = 0
        self.t_until = 0.0
        self._last_family_seen = None

    # ----- helpers --------------------------------------------------------
    def _event(self, t, kind, severity, detail):
        return make_event(t, kind, severity, detail, self.run_id, self.node_id)

    def _start_action(self, t, family, dec):
        sev = _SEVERITY_OF[family]
        self.family = family
        self.t_action = t
        self.t_deadline = t + self.p["verify_s"][family]
        self.healthy_streak = 0
        self.state = "VERIFYING"
        self.phase = "soft" if family == "RESTART" else None
        action = "SOFT_RESET" if family == "RESTART" else family
        dec.action = action
        dec.events.append(self._event(t, "action_taken", sev, action.lower()))
        if family == "ISOLATE":
            dec.events.append(self._event(t, "node_isolated", sev, "relay"))
        if family == "FW_ROLLBACK":
            dec.events.append(self._event(t, "fw_rollback", sev, "FW_ROLLBACK sent"))
        if self.last_sev != sev:
            dec.events.append(self._event(t, "severity_change", sev, f"{self.last_sev}->{sev}"))
            self.last_sev = sev

    # ----- main entry point -----------------------------------------------
    def step(self, t, flags, ctx):
        dec = Decision(state=self.state, severity=self.last_sev)
        # An isolated node is silent on purpose: do not treat that as a fault.
        f = replace(flags, hb_missed=False) if ctx.isolated else flags
        self.anomaly_streak = self.anomaly_streak + 1 if f.anomaly else 0

        if self.state == "MONITORING":
            self._monitoring(t, f, ctx, dec)
        elif self.state == "VERIFYING":
            self._verifying(t, f, dec)
        elif self.state == "ISOLATED_HOLD":
            if t >= self.t_until:
                dec.action = "RESTORE"
                dec.events.append(self._event(t, "node_restored", "NORMAL", "relay on, hard reset"))
                self.state = "COOLDOWN"
                self.t_until = t + self.p["cooldown_s"]
        elif self.state == "COOLDOWN":
            if t >= self.t_until:
                self.state = "MONITORING"
                self.anomaly_streak = 0
        # LATCHED: nothing more to do until reset()
        dec.state = self.state
        dec.severity = self.last_sev
        return dec

    def _monitoring(self, t, f, ctx, dec):
        sev, family, row = classify(
            f, ctx, self.anomaly_streak,
            anomaly_medium_windows=int(round(self.p["anomaly_medium_s"] / self.step_s)),
            anomaly_low_windows=self.p["anomaly_low_windows"])
        dec.row = row
        if sev != self.last_sev:
            if self.last_sev == "NORMAL":
                dec.events.append(self._event(t, "fault_detected", sev, ROW_REASON[row]))
            if not (self.auto_recovery and family in CORRECTIVE):
                dec.events.append(self._event(t, "severity_change", sev, f"{self.last_sev}->{sev}"))
                self.last_sev = sev
        if family == "FLAG_SENSOR" and self._last_family_seen != "FLAG_SENSOR":
            dec.action = "FLAG_SENSOR"
            dec.events.append(self._event(t, "sensor_flagged", sev, "trust=0"))
        self._last_family_seen = family
        if self.auto_recovery and family in CORRECTIVE:
            self._start_action(t, family, dec)

    def _verifying(self, t, f, dec):
        # Restart ladder: soft reset first; if no heartbeat after hard_reset_after_s, pull EN.
        if self.phase == "soft" and t >= self.t_action + self.p["hard_reset_after_s"] - 1e-9:
            self.phase = "done"
            if f.hb_missed:
                dec.action = "HARD_RESET"
                dec.events.append(self._event(t, "action_taken", self.last_sev, "hard_reset"))
        healthy = not (f.anomaly or f.hb_missed or f.flood)
        self.healthy_streak = self.healthy_streak + 1 if healthy else 0
        if self.healthy_streak >= self.p["verify_healthy_windows"]:
            dec.events.append(self._event(t, "verify_ok", self.last_sev, self.family.lower()))
            dec.events.append(self._event(t, "severity_change", "NORMAL", f"{self.last_sev}->NORMAL"))
            self.last_sev = "NORMAL"
            self._last_family_seen = None
            if self.family == "ISOLATE":
                self.state = "ISOLATED_HOLD"
                self.t_until = t + self.p["isolation_hold_s"]
            else:
                self.state = "COOLDOWN"
                self.t_until = t + self.p["cooldown_s"]
        elif t > self.t_deadline + 1e-9:
            dec.events.append(self._event(t, "verify_failed", self.last_sev, self.family.lower()))
            nxt = _ESCALATION.get(self.family)
            if nxt is None:  # SAFE_MODE failed: nothing left to try
                self.state = "LATCHED"
                dec.events.append(self._event(t, "escalate", "CRITICAL", "latched, alert"))
            else:
                dec.events.append(self._event(t, "escalate", _SEVERITY_OF[nxt],
                                              f"{self.family.lower()}->{nxt.lower()}"))
                self._start_action(t, nxt, dec)
