from core import can_codec as c


def test_every_payload_is_8_bytes():
    assert len(c.encode_hb(1, 5, 1, 0, 1234)) == 8
    assert len(c.encode_fwinfo(1, 0, 0, 3, 1)) == 8
    assert len(c.encode_imu(10, 0, 0, 1000)) == 8
    assert len(c.encode_sup_hb(3, 0)) == 8
    assert len(c.encode_sup_cmd(1, 6, 2000)) == 8


def test_heartbeat_roundtrip_and_little_endian_uptime():
    d = c.encode_hb(1, 300, 2, 1, 0x01020304)
    assert d[4:8] == bytes([0x04, 0x03, 0x02, 0x01])      # least significant byte first
    out = c.decode_hb(d)
    assert out == {"node_id": 1, "counter": 300 & 0xFF, "state_code": 2, "bank": 1,
                   "uptime_ms": 0x01020304}


def test_imu_roundtrip_negative_and_clamp():
    out = c.decode_imu(c.encode_imu(-1234, 5, -6, 1000))
    assert out == {"gz_cdps": -1234, "ax_mg": 5, "ay_mg": -6, "az_mg": 1000}
    assert c.decode_imu(c.encode_imu(99999, 0, 0, 0))["gz_cdps"] == 32767


def test_fwinfo_and_cmd_roundtrip():
    out = c.decode_fwinfo(c.encode_fwinfo(1, 1, 1, 2, 3))
    assert out == {"version": (1, 1, 1), "ota_code": 2, "build_id": 3}
    cmd = c.decode_sup_cmd(c.encode_sup_cmd(0xFF, 0x06, 2000))
    assert cmd == {"target": 0xFF, "cmd_code": 6, "arg": 2000}
