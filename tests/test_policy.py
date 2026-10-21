import pytest

from core.config import load_config
from core.policy import Flags, Context, PolicyEngine, classify

CFG = load_config()
STEP = 0.1


def kinds(events):
    return [e["kind"] for e in events]


# ----- the policy table: one test per row ------------------------------------
@pytest.mark.parametrize("flags,ctx,streak,expected", [
    # row 1: canary + any of anomaly / heartbeat missed / flood
    (Flags(anomaly=True), Context(node_state="CANARY"), 1, ("CRITICAL", "FW_ROLLBACK", 1)),
    (Flags(hb_missed=True), Context(node_state="CANARY"), 0, ("CRITICAL", "FW_ROLLBACK", 1)),
    (Flags(flood=True), Context(node_state="CANARY"), 0, ("CRITICAL", "FW_ROLLBACK", 1)),
    # row 2: flood without a test burst; this wins over heartbeat missed
    (Flags(flood=True), Context(), 0, ("HIGH", "ISOLATE", 2)),
    (Flags(flood=True, hb_missed=True), Context(), 0, ("HIGH", "ISOLATE", 2)),
    # row 3
    (Flags(hb_missed=True), Context(), 0, ("MEDIUM", "RESTART", 3)),
    # row 4 / 5
    (Flags(drift="fault"), Context(), 0, ("MEDIUM", "FLAG_SENSOR", 4)),
    (Flags(drift="warn"), Context(), 0, ("LOW", "LOWER_TRUST", 5)),
    # row 6: anomaly needs 3 windows; after 5 s (50 windows) it becomes Medium
    (Flags(anomaly=True), Context(), 2, ("NORMAL", None, 8)),
    (Flags(anomaly=True), Context(), 3, ("LOW", "INCREASE_MONITORING", 6)),
    (Flags(anomaly=True), Context(), 50, ("MEDIUM", "RESTART", 6)),
    # row 7: gateway-started test burst, rate flag or anomaly ignored
    (Flags(flood=True), Context(test_burst=True), 0, ("NORMAL", None, 7)),
    (Flags(anomaly=True), Context(test_burst=True), 10, ("NORMAL", None, 7)),
    # row 8
    (Flags(), Context(), 0, ("NORMAL", None, 8)),
])
def test_policy_table_rows(flags, ctx, streak, expected):
    assert classify(flags, ctx, streak) == expected


def test_heartbeat_missed_during_burst_still_counts():
    assert classify(Flags(hb_missed=True), Context(test_burst=True))[2] == 3


# ----- the engine -----------------------------------------------------------
def drive(engine, t, n, flags, ctx):
    """Run n windows with fixed flags. Returns (new t, list of decisions)."""
    out = []
    for _ in range(n):
        t = round(t + STEP, 6)
        out.append(engine.step(t, flags, ctx))
    return t, out


def actions(decisions):
    return [d.action for d in decisions if d.action]


def all_events(decisions):
    return [e for d in decisions for e in d.events]


def test_flood_isolate_verify_hold_restore():
    e = PolicyEngine(CFG)
    t, d1 = drive(e, 0, 1, Flags(flood=True), Context())
    assert actions(d1) == ["ISOLATE"] and d1[0].severity == "HIGH"
    assert kinds(d1[0].events)[:2] == ["fault_detected", "action_taken"]
    t, d2 = drive(e, t, 9, Flags(flood=True), Context(isolated=True))     # still flooding in window
    assert "verify_ok" not in kinds(all_events(d2))
    t, d3 = drive(e, t, 10, Flags(), Context(isolated=True))              # window now clean
    assert "verify_ok" in kinds(all_events(d3))
    assert e.state == "ISOLATED_HOLD"
    t, d4 = drive(e, t, 101, Flags(), Context(isolated=True))
    assert actions(d4) == ["RESTORE"] and "node_restored" in kinds(all_events(d4))
    t, _ = drive(e, t, 21, Flags(), Context())
    assert e.state == "MONITORING"


def test_hang_restart_ladder_soft_then_hard_then_verify():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 1, Flags(hb_missed=True), Context())
    assert actions(d)[0] == "SOFT_RESET"
    t, d = drive(e, t, 9, Flags(hb_missed=True), Context())
    assert actions(d) == []                                               # still waiting
    t, d = drive(e, t, 1, Flags(hb_missed=True), Context())
    assert actions(d) == ["HARD_RESET"]                                   # 1 s later, no heartbeat
    t, d = drive(e, t, 10, Flags(), Context())
    assert "verify_ok" in kinds(all_events(d))


def test_soft_reset_that_works_never_needs_hard_reset():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 1, Flags(hb_missed=True), Context())
    t, d = drive(e, t, 3, Flags(hb_missed=True), Context())
    t, d = drive(e, t, 30, Flags(), Context())                            # node came back
    assert "HARD_RESET" not in actions(d)
    assert "verify_ok" in kinds(all_events(d))


def test_escalation_restart_to_isolate_to_safe_mode_to_latched():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 1, Flags(hb_missed=True), Context())
    assert d[0].severity == "MEDIUM"
    t, d = drive(e, t, 55, Flags(hb_missed=True), Context())              # > 5 s, never healthy
    ev = all_events(d)
    assert "verify_failed" in kinds(ev) and "escalate" in kinds(ev)
    assert "ISOLATE" in actions(d)
    t, d = drive(e, t, 40, Flags(flood=True), Context(isolated=True))     # isolation verify fails (3 s)
    assert "SAFE_MODE" in actions(d) and d[-1].severity == "CRITICAL"
    t, d = drive(e, t, 60, Flags(flood=True), Context(isolated=True))
    assert e.state == "LATCHED"
    t, d = drive(e, t, 20, Flags(flood=True), Context(isolated=True))
    assert actions(d) == []                                               # no flapping once latched


def test_canary_rollback_then_verify():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 1, Flags(flood=True), Context(node_state="CANARY"))
    assert actions(d) == ["FW_ROLLBACK"] and d[0].severity == "CRITICAL"
    assert "fw_rollback" in kinds(d[0].events)
    t, d = drive(e, t, 10, Flags(), Context(node_state="RUN"))
    assert "verify_ok" in kinds(all_events(d))


def test_cooldown_blocks_new_actions_right_after_a_fix():
    e = PolicyEngine(CFG)
    t, _ = drive(e, 0, 1, Flags(hb_missed=True), Context())
    t, d = drive(e, t, 12, Flags(), Context())
    assert e.state == "COOLDOWN"
    t, d = drive(e, t, 5, Flags(hb_missed=True), Context())               # fault again inside cooldown
    assert actions(d) == []
    t, d = drive(e, t, 30, Flags(hb_missed=True), Context())              # cooldown over: acts again
    assert actions(d)[0] == "SOFT_RESET"


def test_drift_is_flagged_once_and_never_escalates():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 600, Flags(drift="fault"), Context())
    assert actions(d) == ["FLAG_SENSOR"]
    assert kinds(all_events(d)).count("sensor_flagged") == 1
    assert e.state == "MONITORING"
    assert "verify_failed" not in kinds(all_events(d))
    t, d = drive(e, t, 1, Flags(), Context())
    assert d[0].severity == "NORMAL"


def test_anomaly_alone_low_then_medium_after_five_seconds():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 3, Flags(anomaly=True), Context())
    assert d[-1].severity == "LOW" and actions(d) == []
    t, d = drive(e, t, 60, Flags(anomaly=True), Context())
    assert "SOFT_RESET" in actions(d)


def test_auto_recovery_off_reports_but_never_acts():
    e = PolicyEngine(CFG, auto_recovery=False)
    t, d = drive(e, 0, 50, Flags(flood=True), Context())
    assert actions(d) == []
    ev = kinds(all_events(d))
    assert ev.count("fault_detected") == 1 and "action_taken" not in ev
    assert d[-1].severity == "HIGH" and e.state == "MONITORING"


def test_test_burst_context_keeps_everything_normal():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 50, Flags(flood=True, anomaly=True), Context(test_burst=True))
    assert actions(d) == [] and all_events(d) == []
    assert all(x.severity == "NORMAL" for x in d)


def test_isolated_node_silence_is_not_a_fault():
    e = PolicyEngine(CFG)
    t, d = drive(e, 0, 30, Flags(hb_missed=True), Context(isolated=True))
    assert actions(d) == [] and all_events(d) == []


def test_event_shape_matches_contract():
    e = PolicyEngine(CFG, run_id=7)
    _, d = drive(e, 0, 1, Flags(flood=True), Context())
    ev = d[0].events[0]
    assert set(ev) == {"type", "v", "t_ms", "run_id", "kind", "node", "severity", "detail"}
    assert ev["type"] == "event" and ev["v"] == 1 and ev["run_id"] == 7 and ev["t_ms"] == 100
