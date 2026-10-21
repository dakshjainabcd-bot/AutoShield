"""Simulator parameters. These are PLACEHOLDERS: replace the timing and noise
numbers with measured values after the Phase 4 hardware logs (roadmap 1.3).
"""

SIM_DEFAULTS = {
    "dt": 0.01,                 # internal tick, seconds
    "hb_jitter_s": 0.0005,      # node heartbeat timing noise (std)
    "imu_jitter_s": 0.0003,
    "gw_jitter_s": 0.0003,
    "fwinfo_jitter_s": 0.0005,
    "boot_time_s": 0.5,         # silent time after any reset
    "soft_reset_delay_s": 0.1,  # command received -> reboot starts
    "flood_rate_hz": 1500.0,    # frames/s of ID 0x050 during a flood
    "burst_rate_hz": 500.0,     # frames/s of ID 0x1F0 during a test burst
    "imu_noise_cdps": 8.0,      # gyro noise (std), centi-deg/s
    "motion_amp_cdps": 500.0,   # gentle sinusoidal motion
    "motion_period_s": 20.0,
    # faulty firmware (image 1.1.1)
    "faulty_hb_delay_max_s": 0.05,   # extra random delay on each heartbeat
    "faulty_burst_after_s": 3.0,     # first burst this long after boot
    "faulty_burst_every_s": 1.0,
    "faulty_burst_frames": 30,
    "faulty_burst_span_s": 0.05,
    "faulty_burst_id": 0x3A0,        # NOT in the catalogue
}
