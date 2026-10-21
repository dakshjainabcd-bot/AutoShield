"""The contract examples must parse and agree with the code."""
import json
from pathlib import Path

from core import catalogue as C
from core.features import FEATURE_NAMES
from core.policy import Flags, Context, PolicyEngine

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


def load(name):
    with open(CONTRACTS / "examples" / name, encoding="utf-8") as fh:
        return json.load(fh)


def test_telemetry_example_has_all_contract_fields():
    t = load("telemetry.json")
    assert set(t) == {"type", "v", "mode", "t_ms", "run_id", "bus", "features", "ml", "monitors",
                      "nodes", "sensor", "context", "severity", "action"}
    assert t["mode"] in ("sim", "hw") and t["severity"] in C.SEVERITIES
    assert len(t["features"]) == len(FEATURE_NAMES) == 6


def test_event_example_matches_events_made_by_the_policy_engine():
    example = load("event.json")
    e = PolicyEngine(run_id=7)
    dec = e.step(0.1, Flags(flood=True), Context())
    assert set(dec.events[0]) == set(example)


def test_catalogue_matches_contract_numbers():
    assert C.HEALTHY_FPS == 71.0
    assert C.CMD_CODES["TEST_BURST"] == 0x06 and C.CMD_CODES["SAFE_MODE"] == 0x07
    assert C.NODE_STATE_CODES == {"BOOT": 0, "RUN": 1, "CANARY": 2, "SAFE": 3}


def test_all_four_contract_files_exist():
    for name in ("can_catalogue.md", "telemetry_schema.md", "harness_commands.md", "api.md"):
        assert (CONTRACTS / name).is_file()
