"""CAN catalogue constants (contracts/can_catalogue.md, contract version 1).

Classic CAN, 11-bit IDs, 500 kbit/s. Lower ID = higher priority.
"""

BITRATE = 500_000

ID_SUP_CMD = 0x010      # gateway -> nodes, on event
ID_SUP_HB = 0x020       # gateway heartbeat, 100 ms
ID_SPAM = 0x050         # faults only (flood injection)
ID_NODE_HB = 0x100      # node 1 heartbeat, 100 ms
ID_NODE_FWINFO = 0x110  # node 1 firmware info, 1 s and at boot
ID_TEST_BURST = 0x1F0   # node 1, only during a gateway-started test burst
ID_NODE_IMU = 0x200     # node 1 IMU, 20 ms

# Expected rate in frames per second for the periodic IDs of a healthy bus.
# 10 + 10 + 1 + 50 = 71 frames per second.
EXPECTED_RATE_HZ = {
    ID_SUP_HB: 10.0,
    ID_NODE_HB: 10.0,
    ID_NODE_FWINFO: 1.0,
    ID_NODE_IMU: 50.0,
}

HEALTHY_FPS = sum(EXPECTED_RATE_HZ.values())  # 71.0

# Supervisor command codes (byte 1 of 0x010)
CMD_SOFT_RESET = 0x01
CMD_SILENCE = 0x02
CMD_RESUME = 0x03
CMD_FW_COMMIT = 0x04
CMD_FW_ROLLBACK = 0x05
CMD_TEST_BURST = 0x06
CMD_SAFE_MODE = 0x07

CMD_CODES = {
    "SOFT_RESET": CMD_SOFT_RESET,
    "SILENCE": CMD_SILENCE,
    "RESUME": CMD_RESUME,
    "FW_COMMIT": CMD_FW_COMMIT,
    "FW_ROLLBACK": CMD_FW_ROLLBACK,
    "TEST_BURST": CMD_TEST_BURST,
    "SAFE_MODE": CMD_SAFE_MODE,
}

# Node state codes (0x100 byte 2). SILENT and HUNG exist only inside the
# simulator; they are never sent on the wire.
NODE_STATE_CODES = {"BOOT": 0, "RUN": 1, "CANARY": 2, "SAFE": 3}
NODE_STATE_NAMES = {v: k for k, v in NODE_STATE_CODES.items()}

# OTA state codes (0x110 byte 3)
OTA_STATE_CODES = {"UNKNOWN": 0, "NEW": 1, "PENDING_VERIFY": 2, "VALID": 3, "INVALID": 4}
OTA_STATE_NAMES = {v: k for k, v in OTA_STATE_CODES.items()}

SEVERITIES = ["NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
