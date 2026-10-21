# Team pin sheet (starts in Phase 0, finished in Phase 4)

## Pins you must NOT use

| Board | Do not use | Reason |
| --- | --- | --- |
| ESP32-S3 | GPIO0, GPIO3, GPIO45, GPIO46 | strapping pins (affect boot) |
| ESP32-S3 | GPIO26 to GPIO32 | flash / PSRAM |
| ESP32-S3 | GPIO35, GPIO36, GPIO37 | octal flash / PSRAM on some variants; never use, whichever variant you have |
| ESP32-S3 | GPIO43, GPIO44 | console serial (TX/RX) |
| ESP32-S3 | GPIO19, GPIO20 | native USB D- / D+ (check on your machine; avoid if you use the native USB port) |
| ESP32 classic | GPIO6 to GPIO11 | flash |
| ESP32 classic | GPIO0, 2, 5, 12, 15 | strapping pins; use with care |
| ESP32 classic | GPIO34 to GPIO39 | input only (cannot drive outputs) |

Check every pin against your own board's pin diagram before wiring.

## Assignments (fill in Phase 4; copy the SPI/I2C numbers printed by board_info)

| Function | Gateway (ESP32-S3) | Target (ESP32) |
| --- | --- | --- |
| SPI SS / MOSI / MISO / SCK | | |
| MCP2515 INT (via 5 V to 3.3 V divider) | GPIO4 suggested | GPIO4 suggested |
| I2C SDA / SCL | | |
| Relay control | | n/a |
| EN reset line to target | | n/a |
| LEDs / buzzer driver / button | | |
