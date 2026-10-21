import numpy as np
import pytest

from core.frames import Frame
from core.monitors import HeartbeatMonitor, RateMonitor, DriftMonitor


# ----- heartbeat deadline ---------------------------------------------------
def test_heartbeat_just_under_and_just_over_deadline():
    m = HeartbeatMonitor(300)
    m.observe(Frame(1.0, 0x100, 8))
    assert not m.missed(1.299)
    assert not m.missed(1.300)        # exactly 300 ms is not 'greater than'
    assert m.missed(1.301)
    assert m.age_ms(1.25) == pytest.approx(250.0)


def test_heartbeat_ignores_other_ids_and_recovers():
    m = HeartbeatMonitor(300)
    m.observe(Frame(1.0, 0x200, 8))
    assert m.missed(1.5)              # no node heartbeat ever seen
    m.observe(Frame(1.4, 0x100, 8))
    assert not m.missed(1.5)


# ----- per-ID rate ----------------------------------------------------------
def window_of(can_id, n):
    return [Frame(0.5 + i * 0.5 / max(n, 1), can_id, 8) for i in range(n)]


def normal_window():
    return window_of(0x100, 10) + window_of(0x200, 50) + window_of(0x020, 10) + window_of(0x110, 1)


def test_rate_quiet_on_normal_traffic():
    m = RateMonitor()
    for _ in range(20):
        assert not m.update(normal_window())


def test_rate_flags_unknown_id_after_three_windows_in_a_row():
    m = RateMonitor()
    w = normal_window() + window_of(0x050, 25)      # 25 fps > 20 fps limit
    assert not m.update(w) and not m.update(w)
    assert m.update(w)                              # third consecutive window
    assert m.offenders == {0x050}


def test_rate_just_under_unknown_limit_is_fine_and_streak_resets():
    m = RateMonitor()
    under = normal_window() + window_of(0x050, 20)   # exactly 20 fps: not above
    for _ in range(5):
        assert not m.update(under)
    over = normal_window() + window_of(0x050, 25)
    m.update(over); m.update(over)
    m.update(normal_window())                        # streak broken
    assert not m.update(over)


def test_rate_known_id_limit_is_three_times_expected():
    m = RateMonitor()
    ok = window_of(0x100, 30)                        # 30 fps = 3 x 10: not above
    for _ in range(5):
        assert not m.update(ok)
    bad = window_of(0x100, 31)
    m.update(bad); m.update(bad)
    assert m.update(bad)


def test_rate_test_burst_id_ignored_only_during_burst():
    m = RateMonitor()
    w = normal_window() + window_of(0x1F0, 500)
    for _ in range(5):
        assert not m.update(w, test_burst_active=True)
    m2 = RateMonitor()
    m2.update(w); m2.update(w)
    assert m2.update(w)                              # same traffic, no context: flood


# ----- sensor drift ---------------------------------------------------------
def test_drift_quiet_on_noise():
    rng = np.random.default_rng(0)
    m = DriftMonitor()
    states = {m.update(float(rng.normal(0, 5))) for _ in range(20000)}
    assert states == {"ok"}
    assert m.trust() > 0.5


def test_drift_ramp_goes_warn_then_fault_and_trust_falls():
    m = DriftMonitor()
    seen = []
    for k in range(1, 100):
        s = m.update(5.0 * k)            # residual ramps up 5 cdps per window
        if not seen or seen[-1] != s:
            seen.append(s)
    assert seen == ["ok", "warn", "fault"]
    assert m.trust() == 0.0


def test_drift_none_keeps_state_and_decays_back_to_ok():
    m = DriftMonitor()
    for _ in range(60):
        m.update(200.0)
    assert m.state == "fault"
    assert m.update(None) == "fault"
    for _ in range(200):
        m.update(0.0)
    assert m.state == "ok"
