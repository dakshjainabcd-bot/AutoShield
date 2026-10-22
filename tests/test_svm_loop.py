"""Phase 2 gate: the SVM plugged into the closed loop (supervisor + simulator)."""
import pytest

from core.model import SvmModel, MODEL_PATH
from sim.runner import run_closed_loop
from sim.scenarios import DEFAULT_SCENARIO, DEFAULT_DURATION

needs_model = pytest.mark.skipif(not MODEL_PATH.exists(), reason="run python -m ml.train first")


class AlwaysAnomalous:
    """Stub detector: every window is anomalous."""
    threshold = 0.0

    def anomaly_score(self, features):
        return 1.0


def kinds(res, kind=None):
    return [e for e in res.events if kind is None or e["kind"] == kind]


def test_no_detector_means_phase_1_behaviour():
    res = run_closed_loop([], 20.0, seed=1)
    assert all(s.anomaly_score == 0.0 and not s.anomaly_raw for s in res.steps)


def test_stub_anomaly_alone_gives_low_after_three_windows():
    res = run_closed_loop([], 10.0, seed=1, detector=AlwaysAnomalous())
    det = kinds(res, "fault_detected")
    assert det and det[0]["detail"] == "svm_anomaly" and det[0]["severity"] == "LOW"
    assert det[0]["t_ms"] == 1200          # first evaluated window 1.0 s, 3rd flagged window 1.2 s


def test_boot_grace_ignores_the_anomaly_so_a_booting_canary_is_not_rolled_back():
    res = run_closed_loop([(10.0, "faulty_fw", {})], 16.0, seed=1, detector=AlwaysAnomalous())
    rollback = [e for e in kinds(res, "action_taken") if e["detail"] == "fw_rollback"]
    assert rollback and rollback[0]["t_ms"] >= 12000        # deploy at 10 s + 2 s grace


def test_isolated_node_silence_is_not_an_svm_anomaly():
    res = run_closed_loop([(10.0, "flood", {"duration_s": 5.0})], 40.0, seed=1,
                          detector=AlwaysAnomalous())
    assert [e for e in kinds(res, "verify_ok") if e["detail"] == "isolate"]


@needs_model
def test_full_scenario_with_svm_keeps_every_recovery():
    m = SvmModel.load()
    res = run_closed_loop(DEFAULT_SCENARIO, DEFAULT_DURATION, seed=1, detector=m)

    def has(kind, t0, t1, detail=None):
        return [e for e in res.events if e["kind"] == kind and t0 <= e["t_ms"] / 1000 < t1
                and (detail is None or e["detail"] == detail)]
    assert has("fault_detected", 60, 61, "flood") and has("verify_ok", 60, 65, "isolate")
    assert has("node_restored", 70, 80)
    assert has("fault_detected", 90, 91, "heartbeat_missed") and has("verify_ok", 90, 100, "restart")
    assert has("sensor_flagged", 120, 125)
    assert has("fault_detected", 150, 156, "canary_unhealthy") and has("verify_ok", 150, 160, "fw_rollback")
    assert res.sim.node.version == (1, 0, 0) and res.sim.node.state == "RUN"
    assert not [e for e in res.events if 170 <= e["t_ms"] / 1000 <= 176
                and e["kind"] in ("fault_detected", "action_taken")]       # test burst: context rule


@needs_model
def test_svm_gives_no_false_alarms_on_ten_minutes_of_fresh_healthy_traffic():
    m = SvmModel.load()
    res = run_closed_loop([], 600.0, seed=4242, detector=m)
    assert res.events == []
    assert all(s.decision.severity == "NORMAL" for s in res.steps)


@needs_model
def test_svm_sees_the_flood_and_the_test_burst_but_context_suppresses_the_burst():
    m = SvmModel.load()
    res = run_closed_loop([(20.0, "test_burst", {"duration_s": 2.0})], 30.0, seed=7, detector=m,
                          auto_recovery=True)
    burst = [s for s in res.steps if 20.5 <= s.t <= 22.0]
    assert all(s.anomaly_raw for s in burst)                         # the SVM does flag it
    assert all(s.decision.severity == "NORMAL" for s in res.steps)   # the policy does not care
