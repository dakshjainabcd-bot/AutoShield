"""Encode and decode the 8-byte payloads of the CAN catalogue.

All multi-byte numbers are little-endian (least significant byte first).
The struct format strings start with '<' for exactly that reason: '<' also
means "no padding", so every payload is exactly 8 bytes.
"""
import struct


def _i16(v):
    """Clamp to the signed 16-bit range."""
    return max(-32768, min(32767, int(round(v))))


# 0x100 NODE1_HB: node id, counter, state, bank, uptime ms (uint32)
def encode_hb(node_id, counter, state_code, bank, uptime_ms):
    return struct.pack("<BBBBI", node_id, counter & 0xFF, state_code, bank,
                       int(uptime_ms) & 0xFFFFFFFF)


def decode_hb(data):
    node_id, counter, state_code, bank, uptime_ms = struct.unpack("<BBBBI", data)
    return {"node_id": node_id, "counter": counter, "state_code": state_code,
            "bank": bank, "uptime_ms": uptime_ms}


# 0x110 NODE1_FWINFO: major, minor, patch, ota state, build id (uint16), 2 zero bytes
def encode_fwinfo(major, minor, patch, ota_code, build_id):
    return struct.pack("<BBBBHH", major, minor, patch, ota_code, build_id, 0)


def decode_fwinfo(data):
    major, minor, patch, ota_code, build_id, _ = struct.unpack("<BBBBHH", data)
    return {"version": (major, minor, patch), "ota_code": ota_code, "build_id": build_id}


# 0x200 NODE1_IMU: gyro_z (centi-deg/s), ax, ay, az (milli-g), all int16
def encode_imu(gz_cdps, ax_mg, ay_mg, az_mg):
    return struct.pack("<hhhh", _i16(gz_cdps), _i16(ax_mg), _i16(ay_mg), _i16(az_mg))


def decode_imu(data):
    gz, ax, ay, az = struct.unpack("<hhhh", data)
    return {"gz_cdps": gz, "ax_mg": ax, "ay_mg": ay, "az_mg": az}


# 0x020 SUP_HB: rolling counter, gateway mode, 6 zero bytes
def encode_sup_hb(counter, mode):
    return struct.pack("<BB6x", counter & 0xFF, mode)


def decode_sup_hb(data):
    counter, mode = struct.unpack("<BB6x", data)
    return {"counter": counter, "mode": mode}


# 0x010 SUP_CMD: target node (0xFF = all), command code, uint16 argument, 4 zero bytes
def encode_sup_cmd(target, cmd_code, arg=0):
    return struct.pack("<BBH4x", target, cmd_code, arg & 0xFFFF)


def decode_sup_cmd(data):
    target, cmd_code, arg = struct.unpack("<BBH4x", data)
    return {"target": target, "cmd_code": cmd_code, "arg": arg}
