"""Simulated vehicle network (roadmap steps 1.2 to 1.5).

VehicleSim generates the frames of a healthy bus and lets you inject the four
faults and react to gateway commands, exactly like the real node will:

    sim = VehicleSim(seed=1)
    frames, ref = sim.advance(1.0)        # simulate up to t = 1.0 s
    sim.inject("flood", duration_s=5)
    sim.command("ISOLATE")

Time runs in fixed ticks of 10 ms, so the same seed always gives the same traffic.
"""
import math

import numpy as np

from core import catalogue as C
from core import can_codec as codec
from core.frames import Frame
from sim.params import SIM_DEFAULTS

NODE_ID = 1
STATE_CODE = {"RUN": 1, "CANARY": 2, "SAFE": 3}
IMAGES = {  # name -> (version, build id, is_faulty)
    "good": ((1, 1, 0), 2, False),
    "faulty": ((1, 1, 1), 3, True),
}


class PeriodicSource:
    """Hands out nominal send times k * period."""

    def __init__(self, period, first=None):
        self.period = period
        self.next = period if first is None else first

    def restart(self, t_from, immediate=False):
        self.next = t_from if immediate else t_from + self.period

    def due(self, t1):
        out = []
        while self.next < t1 - 1e-12:
            out.append(self.next)
            self.next += self.period
        return out


class NodeSim:
    """Target node state machine: BOOT, RUN, CANARY, SAFE, HUNG (isolation is a
    relay on the bus, handled by VehicleSim; see VehicleSim.state_label)."""

    def __init__(self, p, rng, truth):
        self.p, self.rng, self.truth = p, rng, truth
        self.hb = PeriodicSource(0.1)
        self.imu = PeriodicSource(0.02)
        self.fwinfo = PeriodicSource(1.0)
        self.state = "RUN"
        self.bank = 0
        self.version, self.build, self.faulty = (1, 0, 0), 1, False
        self.ota = "VALID"
        self.canary = False
        self.prev = None            # image to fall back to while canary
        self.counter = 0
        self.boot_t = 0.0
        self.silenced = False
        self.hang_boots = 0         # reboots that hang again immediately
        self.reboot_at = None
        self.boot_done_at = None
        self.flood_until = None
        self.flood_rate = p["flood_rate_hz"]
        self._flood_acc = 0.0
        self.burst_until = None
        self._burst_acc = 0.0
        self.drift_slope = 0.0
        self.drift_t0 = None
        self.next_fault_burst = None

    # ----- images, boot ----------------------------------------------------
    def _snapshot(self):
        return (self.bank, self.version, self.build, self.faulty)

    def _rollback_image(self):
        self.bank, self.version, self.build, self.faulty = self.prev
        self.prev, self.canary, self.ota = None, False, "VALID"

    def _enter_boot(self, t):
        self.reboot_at = None
        self.flood_until = self.burst_until = None
        self.drift_slope, self.drift_t0 = 0.0, None
        self.silenced = False
        self.state = "BOOT"
        self.boot_done_at = t + self.p["boot_time_s"]

    def _reboot(self, t):
        # Bootloader rule: a reset before the new image is confirmed rolls back.
        if self.canary:
            self._rollback_image()
        self._enter_boot(t)

    def _finish_boot(self, t0):
        self.boot_done_at = None
        if self.hang_boots > 0:
            self.hang_boots -= 1
            self.state = "HUNG"
            return
        self.state = "CANARY" if self.canary else "RUN"
        self.boot_t = t0
        self.hb.restart(t0)
        self.imu.restart(t0)
        self.fwinfo.restart(t0, immediate=True)      # firmware info is sent at boot
        self.next_fault_burst = (t0 + self.p["faulty_burst_after_s"]) if self.faulty else None

    def deploy(self, t, image):
        if self.state in ("HUNG", "BOOT"):
            return
        version, build, faulty = IMAGES[image]
        self.prev = self._snapshot()
        self.bank ^= 1
        self.version, self.build, self.faulty = version, build, faulty
        self.canary, self.ota = True, "PENDING_VERIFY"
        self._enter_boot(t)

    # ----- commands --------------------------------------------------------
    def can_command(self, t, name, arg=0):
        """Commands that arrive as CAN frames: a hung or booting node cannot hear them."""
        if self.state in ("HUNG", "BOOT"):
            return
        if name == "SOFT_RESET":
            self.reboot_at = t + self.p["soft_reset_delay_s"]
        elif name == "SILENCE":
            self.silenced = True
        elif name == "RESUME":
            self.silenced = False
        elif name == "FW_COMMIT":
            if self.canary:
                self.canary, self.ota, self.prev = False, "VALID", None
                if self.state == "CANARY":
                    self.state = "RUN"
        elif name == "FW_ROLLBACK":
            if self.canary:
                self._rollback_image()
                self.reboot_at = t + self.p["soft_reset_delay_s"]
        elif name == "TEST_BURST":
            self.burst_until = t + arg / 1000.0
        elif name == "SAFE_MODE":
            self.state = "SAFE"

    def hard_reset(self, t):
        """EN line pulled low: works even if the node is hung."""
        self.reboot_at = t

    # ----- faults ----------------------------------------------------------
    def inject_flood(self, t, duration_s, rate_hz=None):
        self.flood_until = t + duration_s
        self.flood_rate = rate_hz or self.p["flood_rate_hz"]

    def inject_hang(self, boots=0):
        self.state = "HUNG"
        self.hang_boots = boots

    def inject_drift(self, t, slope):
        self.drift_slope, self.drift_t0 = slope, t

    def clear(self):
        """Harness CLEAR: remove flood, drift and any future hang. A hung node
        cannot hear its own serial, so a current hang stays."""
        self.flood_until = None
        self.drift_slope, self.drift_t0 = 0.0, None
        self.hang_boots = 0

    # ----- one tick --------------------------------------------------------
    def tick(self, t0, t1):
        p, rng = self.p, self.rng
        if self.reboot_at is not None and t0 >= self.reboot_at - 1e-12:
            self._reboot(t0)
        if self.state == "BOOT" and t0 >= self.boot_done_at - 1e-12:
            self._finish_boot(t0)
        if self.state in ("BOOT", "HUNG"):
            return []
        out = []
        uptime = int((t0 - self.boot_t) * 1000)
        code = STATE_CODE[self.state]
        for nom in self.hb.due(t1):
            if self.faulty:
                tt = nom + rng.uniform(0.0, p["faulty_hb_delay_max_s"])
            else:
                tt = nom + rng.normal(0.0, p["hb_jitter_s"])
            out.append(Frame(tt, C.ID_NODE_HB, 8,
                             codec.encode_hb(NODE_ID, self.counter, code, self.bank, uptime)))
            self.counter = (self.counter + 1) & 0xFF
        if self.state != "SAFE":      # safe mode: heartbeat only
            for nom in self.imu.due(t1):
                gz = self.truth(nom) + rng.normal(0.0, p["imu_noise_cdps"])
                if self.drift_t0 is not None:
                    gz += self.drift_slope * (nom - self.drift_t0)
                out.append(Frame(nom + rng.normal(0.0, p["imu_jitter_s"]), C.ID_NODE_IMU, 8,
                                 codec.encode_imu(gz, 0, 0, 1000)))
            for nom in self.fwinfo.due(t1):
                out.append(Frame(nom + rng.normal(0.0, p["fwinfo_jitter_s"]), C.ID_NODE_FWINFO, 8,
                                 codec.encode_fwinfo(*self.version, C.OTA_STATE_CODES[self.ota],
                                                     self.build)))
            if self.flood_until is not None:
                out += self._timed_frames(t0, t1, self.flood_until, self.flood_rate,
                                          C.ID_SPAM, "_flood_acc")
                if t1 >= self.flood_until - 1e-12:
                    self.flood_until = None
            if self.burst_until is not None:
                out += self._timed_frames(t0, t1, self.burst_until, p["burst_rate_hz"],
                                          C.ID_TEST_BURST, "_burst_acc")
                if t1 >= self.burst_until - 1e-12:
                    self.burst_until = None
            if self.next_fault_burst is not None and self.next_fault_burst < t1:
                n, span = p["faulty_burst_frames"], p["faulty_burst_span_s"]
                for i in range(n):
                    out.append(Frame(self.next_fault_burst + i * span / n, p["faulty_burst_id"],
                                     8, b"\xAA" * 8))
                self.next_fault_burst += p["faulty_burst_every_s"]
        if self.silenced:
            return []
        return out

    def _timed_frames(self, t0, t1, until, rate, can_id, acc_name):
        span = min(t1, until) - t0
        if span <= 0:
            return []
        acc = getattr(self, acc_name) + rate * span
        n = int(acc)
        setattr(self, acc_name, acc - n)
        times = t0 + (np.arange(n) + self.rng.random(n)) * span / max(n, 1)
        return [Frame(float(x), can_id, 8, b"\xFF" * 8) for x in times]


class VehicleSim:
    def __init__(self, seed=0, params=None):
        self.p = dict(SIM_DEFAULTS)
        if params:
            self.p.update(params)
        self.rng = np.random.default_rng(seed)
        self.dt = self.p["dt"]
        self.k = 0
        self.node = NodeSim(self.p, self.rng, self.truth)
        self.gw_hb = PeriodicSource(0.1)
        self.ref_src = PeriodicSource(0.02)
        self.gw_counter = 0
        self.isolated = False       # the relay: True = node cut off from the bus
        self._cmd_frames = []
        self.ref_samples = []       # everything the reference IMU has produced

    @property
    def t(self):
        return self.k * self.dt

    def truth(self, t):
        """True angular rate (centi-deg/s): a gentle back-and-forth motion."""
        return self.p["motion_amp_cdps"] * math.sin(2 * math.pi * t / self.p["motion_period_s"])

    @property
    def state_label(self):
        return "SILENT" if self.isolated else self.node.state

    # ----- running ---------------------------------------------------------
    def advance(self, t_end):
        """Simulate up to t_end. Returns (frames on the bus, new reference samples)."""
        frames, ref_new = list(self._cmd_frames), []
        self._cmd_frames = []
        n_ticks = int(round((t_end - self.t) / self.dt))
        for _ in range(n_ticks):
            t0, t1 = self.t, (self.k + 1) * self.dt
            node_frames = self.node.tick(t0, t1)
            if not self.isolated:
                frames += node_frames
            for nom in self.gw_hb.due(t1):
                frames.append(Frame(nom + self.rng.normal(0.0, self.p["gw_jitter_s"]),
                                    C.ID_SUP_HB, 8, codec.encode_sup_hb(self.gw_counter, 0)))
                self.gw_counter = (self.gw_counter + 1) & 0xFF
            for nom in self.ref_src.due(t1):
                ref_new.append((nom, self.truth(nom) + self.rng.normal(0.0, self.p["imu_noise_cdps"])))
            self.k += 1
        self.ref_samples += ref_new
        return frames, ref_new

    # ----- faults (what a test bench does to the node) ----------------------
    def inject(self, fault, **kw):
        if fault == "flood":
            self.node.inject_flood(self.t, kw.get("duration_s", 10.0), kw.get("rate_hz"))
        elif fault == "hang":
            self.node.inject_hang(kw.get("boots", 0))
        elif fault == "drift":
            self.node.inject_drift(self.t, kw.get("slope", 50.0))
        elif fault == "faulty_fw":
            self.node.deploy(self.t, "faulty")
        elif fault == "clear":
            self.node.clear()
        else:
            raise ValueError(f"unknown fault: {fault}")

    def deploy(self, image):
        self.node.deploy(self.t, image)

    # ----- gateway actions ---------------------------------------------------
    def command(self, name, **kw):
        t = self.t
        if name in C.CMD_CODES:                     # travels on the bus as a 0x010 frame
            arg = int(kw.get("ms", 0)) if name == "TEST_BURST" else 0
            self._cmd_frames.append(Frame(t, C.ID_SUP_CMD, 8,
                                          codec.encode_sup_cmd(NODE_ID, C.CMD_CODES[name], arg)))
            if not self.isolated:                   # an isolated module cannot hear
                self.node.can_command(t, name, arg)
        elif name == "HARD_RESET":                  # EN line, not on the bus
            self.node.hard_reset(t)
        elif name == "ISOLATE":                     # relay cuts the module's power
            self.isolated = True
        elif name == "RESTORE":                     # relay back, then hard reset (roadmap 4.7)
            self.isolated = False
            self.node.hard_reset(t)
        else:
            raise ValueError(f"unknown command: {name}")
