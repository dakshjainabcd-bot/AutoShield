"""The virtual gateway: telemetry shape (contract) and behaviour."""
import json
from pathlib import Path

import pytest

from backend.gateway import VirtualGateway, BenchError

EXAMPLE = json.loads((Path(__file__).resolve().parent.parent / "contracts" / "examples"
                      / "telemetry.json").read_text())


def run(gw, n):
    tels, evs = [], []
    for _ in range(n):
        t, e = gw.step()
        tels.append(t)
        evs += e
    return tels, evs


def shape(d):
    """Keys of a dict, recursively (lists of dicts use their first item)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = shape(v)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            out[k] = [shape(v[0])]
        else:
            out[k] = None
    return out


def test_telemetry_has_exactly_the_contract_shape():
    tels, _ = run(VirtualGateway(seed=1), 30)
    assert shape(tels[-1]) == shape(EXAMPLE)
    t = tels[-1]
    assert t["type"] == "telemetry" and t["v"] == 1 and t["mode"] == "sim"
    assert len(t["features"]) == 6 and t["severity"] == "NORMAL" and t["action"] is None


def test_healthy_telemetry_values_are_sensible():
    tels, evs = run(VirtualGateway(seed=1), 60)
    t = tels[-1]
    assert t["t_ms"] == 6000 and evs == []
    assert abs(t["bus"]["fps"] - 71) < 3 and abs(t["bus"]["load_pct"] - 1.6) < 0.3
    n = t["nodes"][0]
    assert (n["state"], n["bank"], n["fw"], n["ota_state"], n["isolated"]) == ("RUN", "A", "1.0.0", "VALID", False)
    assert t["sensor"]["trust"] > 0.5 and t["context"] == {"test_burst": False, "auto_recovery": True}


def test_flood_is_detected_isolated_and_shown_in_telemetry():
    gw = VirtualGateway(seed=1)
    run(gw, 30)
    gw.apply("flood", duration_s=3.0)
    tels, evs = run(gw, 40)
    assert [e for e in evs if e["kind"] == "fault_detected" and e["detail"] == "flood"]
    assert any(t["action"] == "ISOLATE" for t in tels)
    assert any(t["nodes"][0]["isolated"] and t["nodes"][0]["state"] == "MISSING" for t in tels)


def test_hang_shows_missing_then_recovers():
    gw = VirtualGateway(seed=1)
    run(gw, 30)
    gw.apply("hang")
    tels, evs = run(gw, 60)
    assert any(t["nodes"][0]["state"] == "MISSING" for t in tels)
    assert [e for e in evs if e["kind"] == "verify_ok"]
    assert tels[-1]["nodes"][0]["state"] == "RUN"


def test_faulty_firmware_is_rolled_back_to_bank_a():
    gw = VirtualGateway(seed=1)
    run(gw, 30)
    gw.apply("faulty_fw")
    tels, evs = run(gw, 80)
    banks = {t["nodes"][0]["bank"] for t in tels}
    assert banks == {"A", "B"}                                   # it ran in bank B, then went back
    assert any(t["nodes"][0]["state"] == "CANARY" and t["nodes"][0]["ota_state"] == "PENDING_VERIFY" for t in tels)
    assert [e for e in evs if e["kind"] == "fw_rollback"]
    assert tels[-1]["nodes"][0]["fw"] == "1.0.0" and tels[-1]["nodes"][0]["bank"] == "A"


def test_deploy_while_hung_is_refused():
    gw = VirtualGateway(seed=1)
    run(gw, 20)
    gw.apply("hang")
    run(gw, 1)
    with pytest.raises(BenchError):
        gw.apply("faulty_fw")


def test_unknown_bench_action_is_refused():
    with pytest.raises(ValueError):
        VirtualGateway().apply("explode")


def test_auto_recovery_off_detects_but_does_not_act():
    gw = VirtualGateway(seed=1)
    gw.set_auto_recovery(False)
    run(gw, 30)
    gw.apply("flood", duration_s=3.0)
    tels, evs = run(gw, 40)
    assert [e for e in evs if e["kind"] == "fault_detected"]
    assert not [e for e in evs if e["kind"] == "action_taken"]
    assert tels[-1]["context"]["auto_recovery"] is False


def test_reset_bench_restarts_the_simulation():
    gw = VirtualGateway(seed=1)
    run(gw, 50)
    gw.apply("hang")
    gw.reset_bench()
    tels, _ = run(gw, 25)
    assert tels[0]["t_ms"] == 100 and tels[-1]["nodes"][0]["state"] == "RUN"


def test_run_id_is_stamped_on_telemetry_and_events():
    gw = VirtualGateway(seed=1)
    gw.set_run_id(5)
    run(gw, 20)
    gw.apply("flood", duration_s=2.0)
    tels, evs = run(gw, 20)
    assert {t["run_id"] for t in tels} == {5} and {e["run_id"] for e in evs} == {5}


def test_same_seed_gives_identical_telemetry():
    a, _ = run(VirtualGateway(seed=3), 40)
    b, _ = run(VirtualGateway(seed=3), 40)
    assert a == b
