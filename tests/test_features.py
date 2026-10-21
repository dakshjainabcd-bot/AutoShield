import pytest

from core.features import window_features, bus_load_pct, select_window
from core.frames import Frame


def hb_trace():
    # five heartbeats exactly 100 ms apart, all inside the window ending at 1.0
    return [Frame(0.55 + 0.1 * i, 0x100, 8) for i in range(5)]


def test_hand_computed_heartbeat_trace():
    f = window_features(hb_trace(), 1.0)
    assert f[0] == 5.0                                   # total_rate
    assert f[1] == 1.0                                   # dominance: only one ID
    assert f[2] == pytest.approx(100.0)                  # hb mean gap
    assert f[3] == pytest.approx(0.0, abs=1e-6)          # hb std gap
    assert f[4] == 1000.0 and f[5] == 0.0                # no IMU frames: defaults


def test_mixed_ids_dominance_and_imu_gaps():
    frames = hb_trace() + [Frame(0.60 + 0.02 * i, 0x200, 8) for i in range(10)]
    f = window_features(frames, 1.0)
    assert f[0] == 15.0
    assert f[1] == pytest.approx(10 / 15)
    assert f[4] == pytest.approx(20.0)


def test_empty_window_and_single_frame_defaults():
    assert window_features([], 1.0) == [0.0, 0.0, 1000.0, 0.0, 1000.0, 0.0]
    f = window_features([Frame(0.5, 0x100, 8)], 1.0)
    assert f[2] == 1000.0 and f[3] == 0.0                # fewer than two frames


def test_window_is_half_open():
    frames = [Frame(0.0, 0x100, 8), Frame(0.5, 0x100, 8), Frame(1.0, 0x100, 8)]
    got = select_window(frames, 1.0, 1.0)
    assert [f.t for f in got] == [0.0, 0.5]              # t_end - W included, t_end excluded


def test_unsorted_frames_give_same_gaps():
    a = hb_trace()
    b = list(reversed(a))
    assert window_features(a, 1.0) == pytest.approx(window_features(b, 1.0))


def test_bus_load_example_from_roadmap():
    assert bus_load_pct(1500) == pytest.approx(33.3, abs=0.01)
