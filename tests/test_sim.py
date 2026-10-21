from collections import Counter

import pytest

from core import can_codec as codec
from core import catalogue as C
from core.features import window_features
from sim.vehicle_sim import VehicleSim


def run(sim, until):
    frames, _ = sim.advance(until)
    return frames


def ids(frames):
    return Counter(f.can_id for f in frames)


def test_healthy_rate_is_about_71_fps():
    frames = run(VehicleSim(seed=1), 300.0)
    assert len(frames) / 300.0 == pytest.approx(71.0, abs=0.5)
    n = ids(frames)
    assert n[C.ID_NODE_IMU] / 300 == pytest.approx(50, abs=0.5)
    assert n[C.ID_NODE_HB] / 300 == pytest.approx(10, abs=0.2)
    assert n[C.ID_SUP_HB] / 300 == pytest.approx(10, abs=0.2)
    assert n[C.ID_NODE_FWINFO] / 300 == pytest.approx(1, abs=0.1)


def test_healthy_features_are_sensible():
    frames = run(VehicleSim(seed=1), 10.0)
    f = window_features(frames, 5.0)
    assert f[0] == pytest.approx(71, abs=2)
    assert f[1] == pytest.approx(0.70, abs=0.03)       # IMU dominates, NOT > 0.5 means flood
    assert f[2] == pytest.approx(100, abs=2) and f[3] < 5
    assert f[4] == pytest.approx(20, abs=1) and f[5] < 3


def test_same_seed_same_traffic_different_seed_differs():
    a = run(VehicleSim(seed=5), 20.0)
    b = run(VehicleSim(seed=5), 20.0)
    c = run(VehicleSim(seed=6), 20.0)
    assert a == b
    assert a != c


def test_advance_in_small_steps_equals_one_big_step():
    s1, s2 = VehicleSim(seed=3), VehicleSim(seed=3)
    big = run(s1, 5.0)
    small = []
    for k in range(1, 51):
        small += run(s2, round(k * 0.1, 6))
    assert sorted(big) == sorted(small)


def test_flood_adds_0x050_at_configured_rate():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.inject("flood", duration_s=1.0)
    frames = run(s, 4.0)
    n = ids(frames)[C.ID_SPAM]
    assert n == pytest.approx(1500, abs=20)
    assert all(2.0 <= f.t <= 3.05 for f in frames if f.can_id == C.ID_SPAM)


def test_hang_silences_node_and_ignores_soft_reset_but_hard_reset_recovers():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.inject("hang")
    frames = run(s, 4.0)
    assert not [f for f in frames if f.can_id in (C.ID_NODE_HB, C.ID_NODE_IMU) and f.t > 2.05]
    s.command("SOFT_RESET")
    frames = run(s, 6.0)
    assert not [f for f in frames if f.can_id == C.ID_NODE_HB]      # hung node cannot hear
    s.command("HARD_RESET")
    frames = run(s, 8.0)
    assert [f for f in frames if f.can_id == C.ID_NODE_HB]          # EN line always works


def test_soft_reset_makes_node_silent_for_boot_time_then_back():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.command("SOFT_RESET")
    frames = run(s, 4.0)
    hb = sorted(f.t for f in frames if f.can_id == C.ID_NODE_HB)
    gaps = [b - a for a, b in zip(hb, hb[1:])]
    assert max(gaps) == pytest.approx(0.1 + 0.1 + 0.5, abs=0.06)   # delay + boot + one period
    assert hb[-1] > 3.8


def test_persistent_hang_survives_reboots():
    s = VehicleSim(seed=1)
    run(s, 1.0)
    s.inject("hang", boots=1)
    run(s, 2.0)
    s.command("HARD_RESET")
    run(s, 4.0)
    assert s.node.state == "HUNG"        # hung again right after boot
    s.command("HARD_RESET")
    run(s, 6.0)
    assert s.node.state == "RUN"


def test_drift_offset_grows_linearly_against_reference():
    s = VehicleSim(seed=1)
    run(s, 5.0)
    s.inject("drift", slope=50.0)
    frames, ref = s.advance(25.0)
    gz = [(f.t, codec.decode_imu(f.data)["gz_cdps"]) for f in frames if f.can_id == C.ID_NODE_IMU]
    late_node = sum(v for t, v in gz if 24 <= t < 25) / 50
    late_ref = sum(v for t, v in ref if 24 <= t < 25) / 50
    assert late_node - late_ref == pytest.approx(50 * 19.5, abs=40)   # about 975 cdps


def test_canary_deploy_commit_and_rollback_paths():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.deploy("good")
    frames = run(s, 4.0)
    hb = [codec.decode_hb(f.data) for f in frames if f.can_id == C.ID_NODE_HB]
    assert hb[-1]["state_code"] == 2 and hb[-1]["bank"] == 1          # CANARY on the other bank
    fw = [codec.decode_fwinfo(f.data) for f in frames if f.can_id == C.ID_NODE_FWINFO]
    assert fw[-1]["version"] == (1, 1, 0) and fw[-1]["ota_code"] == 2  # pending verify
    s.command("FW_COMMIT")
    frames = run(s, 6.0)
    hb = [codec.decode_hb(f.data) for f in frames if f.can_id == C.ID_NODE_HB]
    assert hb[-1]["state_code"] == 1 and hb[-1]["bank"] == 1          # committed, stays
    # explicit rollback
    s2 = VehicleSim(seed=1)
    run(s2, 2.0)
    s2.deploy("faulty")
    run(s2, 4.0)
    s2.command("FW_ROLLBACK")
    frames = run(s2, 7.0)
    hb = [codec.decode_hb(f.data) for f in frames if f.can_id == C.ID_NODE_HB]
    fw = [codec.decode_fwinfo(f.data) for f in frames if f.can_id == C.ID_NODE_FWINFO]
    assert hb[-1]["bank"] == 0 and hb[-1]["state_code"] == 1
    assert fw[-1]["version"] == (1, 0, 0) and fw[-1]["ota_code"] == 3


def test_reset_before_commit_rolls_back_like_the_bootloader():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.deploy("good")
    run(s, 4.0)
    s.command("HARD_RESET")                      # reset without confirming
    frames = run(s, 7.0)
    fw = [codec.decode_fwinfo(f.data) for f in frames if f.can_id == C.ID_NODE_FWINFO]
    assert fw[-1]["version"] == (1, 0, 0)


def test_faulty_firmware_sends_non_catalogue_bursts_after_a_few_seconds():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.deploy("faulty")
    frames = run(s, 12.0)
    bad = [f for f in frames if f.can_id == 0x3A0]
    assert bad and min(f.t for f in bad) > 2.0 + 0.5 + 3.0 - 0.05
    assert len(bad) == 7 * 30          # bursts at 5.5, 6.5 ... 11.5 s


def test_isolation_hides_node_frames_and_restore_brings_them_back():
    s = VehicleSim(seed=1)
    run(s, 2.0)
    s.command("ISOLATE")
    frames = run(s, 4.0)
    assert not [f for f in frames if f.can_id in (C.ID_NODE_HB, C.ID_NODE_IMU)]
    assert [f for f in frames if f.can_id == C.ID_SUP_HB]              # gateway still there
    assert s.state_label == "SILENT"
    s.command("RESTORE")
    frames = run(s, 6.0)
    assert [f for f in frames if f.can_id == C.ID_NODE_HB]


def test_silence_and_resume_and_safe_mode():
    s = VehicleSim(seed=1)
    run(s, 1.0)
    s.command("SILENCE")
    frames = run(s, 2.0)
    assert not [f for f in frames if f.can_id in (C.ID_NODE_HB, C.ID_NODE_IMU)]
    s.command("RESUME")
    run(s, 3.0)
    s.command("SAFE_MODE")
    frames = run(s, 5.0)
    assert not [f for f in frames if f.can_id == C.ID_NODE_IMU and f.t > 3.3]
    hb = [codec.decode_hb(f.data) for f in frames if f.can_id == C.ID_NODE_HB]
    assert hb[-1]["state_code"] == 3


def test_test_burst_sends_0x1f0_for_the_commanded_time():
    s = VehicleSim(seed=1)
    run(s, 1.0)
    s.command("TEST_BURST", ms=2000)
    frames = run(s, 5.0)
    n = ids(frames)[C.ID_TEST_BURST]
    assert n == pytest.approx(1000, abs=20)
    cmd = [f for f in frames if f.can_id == C.ID_SUP_CMD]
    assert len(cmd) == 1 and codec.decode_sup_cmd(cmd[0].data)["arg"] == 2000
