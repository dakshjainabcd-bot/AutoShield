"""Integration tests: simulator + supervisor closed loop (the Phase 1 gate)."""
import json
from pathlib import Path

import pytest

from core import catalogue as C
from sim.runner import run_closed_loop
from sim.scenarios import DEFAULT_SCENARIO, DEFAULT_DURATION, ground_truth


@pytest.fixture(scope="module")
def full():
    return run_closed_loop(DEFAULT_SCENARIO, DEFAULT_DURATION, seed=1)


def ev(res, kind, t_from=0.0, t_to=1e9, detail=None):
    return [e for e in res.events
            if e["kind"] == kind and t_from <= e["t_ms"] / 1000 < t_to
            and (detail is None or e["detail"] == detail)]


def test_healthy_run_has_no_false_alarms_for_ten_minutes():
    res = run_closed_loop([], 600.0, seed=2)
    assert res.events == []
    assert all(s.decision.severity == "NORMAL" for s in res.steps)
    assert max(abs(s.drift_ewma) for s in res.steps) < 10.0          # below the warn limit
    assert all(s.hb_age_ms < 300 for s in res.steps)


def test_healthy_run_rate_features_and_load():
    res = run_closed_loop([], 20.0, seed=2)
    s = res.steps[-1]
    assert s.fps == pytest.approx(71, abs=2) and s.load_pct == pytest.approx(1.6, abs=0.2)
    assert s.features[1] == pytest.approx(0.70, abs=0.03)


def test_flood_detected_isolated_verified_then_restored(full):
    det = ev(full, "fault_detected", 60, 70, "flood")
    assert det and det[0]["t_ms"] / 1000 - 60.0 <= 0.5               # within a few windows
    assert ev(full, "action_taken", 60, 70, "isolate")
    assert ev(full, "node_isolated", 60, 70)
    assert ev(full, "verify_ok", 60, 70, "isolate")
    assert ev(full, "node_restored", 70, 80)


def test_hang_detected_within_deadline_plus_one_window_then_soft_then_hard_reset(full):
    det = ev(full, "fault_detected", 90, 95, "heartbeat_missed")
    assert det and det[0]["t_ms"] / 1000 - 90.0 <= 0.3 + 0.1 + 1e-6
    soft = ev(full, "action_taken", 90, 95, "soft_reset")
    hard = ev(full, "action_taken", 90, 95, "hard_reset")
    assert soft and hard
    assert (hard[0]["t_ms"] - soft[0]["t_ms"]) / 1000 == pytest.approx(1.0, abs=0.11)
    assert ev(full, "verify_ok", 90, 98, "restart")


def test_drift_flagged_and_quiet_after_clear(full):
    assert ev(full, "sensor_flagged", 120, 130)
    assert not ev(full, "action_taken", 120, 150, "isolate")
    last = [s for s in full.steps if 148 <= s.t < 150][-1]
    assert last.decision.severity == "NORMAL" and last.flags.drift == "ok"
    assert last.drift_trust > 0.5
    mid = [s for s in full.steps if 130 <= s.t < 131][-1]
    assert mid.flags.drift == "fault" and mid.drift_trust == 0.0


def test_faulty_firmware_rolled_back_automatically_and_old_image_returns(full):
    assert ev(full, "fw_deploy_started", 150, 151)
    assert not ev(full, "action_taken", 150, 152, "soft_reset")      # boot settling is not a fault
    det = ev(full, "fault_detected", 150, 160, "canary_unhealthy")
    assert det
    assert ev(full, "action_taken", 150, 160, "fw_rollback")
    assert ev(full, "verify_ok", 150, 160, "fw_rollback")
    sim = full.sim
    assert sim.node.version == (1, 0, 0) and sim.node.bank == 0 and sim.node.state == "RUN"
    assert sim.node.ota == "VALID"


def test_gateway_started_test_burst_stays_normal_but_actually_sent_frames(full):
    during = [s for s in full.steps if 170.0 <= s.t <= 174.0]
    assert during and all(s.decision.severity == "NORMAL" for s in during)
    assert max(s.fps for s in during) > 300                          # the burst really happened
    assert ev(full, "test_burst_started") and ev(full, "test_burst_ended")
    assert not [e for e in full.events if 170.0 <= e["t_ms"] / 1000 <= 176.0
                and e["kind"] in ("fault_detected", "action_taken")]


def test_same_traffic_without_context_is_detected_as_flood():
    scenario = [(30.0, "flood", {"duration_s": 2.0, "rate_hz": 500.0})]
    res = run_closed_loop(scenario, 40.0, seed=3)
    assert ev(res, "fault_detected", 30, 35, "flood")


def test_whole_scenario_is_repeatable_with_the_same_seed():
    a = run_closed_loop(DEFAULT_SCENARIO, 100.0, seed=9)
    b = run_closed_loop(DEFAULT_SCENARIO, 100.0, seed=9)
    assert a.events == b.events


def test_persistent_hang_escalates_to_isolation_then_recovers_after_restore():
    scenario = [(20.0, "hang", {"boots": 2})]
    res = run_closed_loop(scenario, 80.0, seed=4)
    assert ev(res, "verify_failed", 20, 40, "restart")
    assert ev(res, "escalate", 20, 40)
    assert ev(res, "action_taken", 20, 40, "isolate")
    assert ev(res, "verify_ok", 20, 45, "isolate")
    assert res.steps[-1].decision.severity == "NORMAL"


def test_auto_recovery_off_detects_and_reports_but_the_flood_keeps_going():
    scenario = [(10.0, "flood", {"duration_s": 5.0})]
    res = run_closed_loop(scenario, 30.0, seed=5, auto_recovery=False)
    assert ev(res, "fault_detected", 10, 12, "flood")
    assert not ev(res, "action_taken")
    assert not res.sim.isolated


def test_ground_truth_list():
    gt = ground_truth(DEFAULT_SCENARIO)
    assert gt == [("flood", 60.0, 70.0), ("hang", 90.0, None),
                  ("drift", 120.0, None), ("faulty_fw", 150.0, None)]


def test_every_event_has_a_known_kind_from_the_contract(full):
    allowed = {"fault_detected", "severity_change", "action_taken", "verify_ok", "verify_failed",
               "escalate", "node_isolated", "node_restored", "test_burst_started",
               "test_burst_ended", "sensor_flagged", "fw_deploy_started", "canary_started",
               "fw_commit", "fw_rollback", "mode_change"}
    assert {e["kind"] for e in full.events} <= allowed
    assert {e["severity"] for e in full.events} <= set(C.SEVERITIES)
