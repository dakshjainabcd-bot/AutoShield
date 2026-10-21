# Target harness commands (contract version 1)

Text lines on the **target's own USB serial**, 115200 baud. Faults are injected here,
not through the supervisor, so the supervisor cannot "know" about a fault in advance (decision D6).

| Command | Effect |
| --- | --- |
| `INJECT FLOOD <ms>` | Send ID 0x050 frames as fast as possible for the given duration |
| `INJECT HANG` | Stop transmitting and listening until reset |
| `INJECT DRIFT <slope>` | Add an offset to the reported gyro_z that grows by `slope` (centi-degrees per second per second) until cleared |
| `CLEAR` | Remove all injected faults (a hung node cannot hear it) |
| `OTA <url>` | Download the image at the URL into the inactive slot and reboot into it |
| `STATUS` | Print version, bank, OTA state and injected faults, each line starting with `#` so the bridge ignores it |

In the simulator (`sim/vehicle_sim.py`) these map to `VehicleSim.inject("flood" | "hang" | "drift" | "clear", ...)`
and `VehicleSim.deploy("good" | "faulty")`.
