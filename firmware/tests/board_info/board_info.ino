// AutoShield Phase 0 - board_info
// Prints chip details and the default SPI / I2C pins of the selected board.
// Wire to the numbers it prints, not to numbers from the internet.
// Set Serial Monitor to 115200 baud.

void setup() {
  Serial.begin(115200);
  delay(2000);

  Serial.println("=== AutoShield board_info ===");
  Serial.printf("Chip model     : %s (revision %d)\n", ESP.getChipModel(), ESP.getChipRevision());
  Serial.printf("CPU cores      : %d\n", ESP.getChipCores());
  Serial.printf("CPU freq (MHz) : %d\n", ESP.getCpuFreqMHz());
  Serial.printf("Flash size (MB): %u\n", ESP.getFlashChipSize() / (1024 * 1024));
  Serial.printf("PSRAM size (B) : %u  (0 = none, or not enabled in Tools > PSRAM)\n", ESP.getPsramSize());
  Serial.printf("Free heap (B)  : %u\n", ESP.getFreeHeap());
  Serial.printf("Core/SDK       : %s\n", ESP.getSdkVersion());
  Serial.println("--- Default pins for the board selected in Tools > Board ---");
  Serial.printf("SPI  SS=%d  MOSI=%d  MISO=%d  SCK=%d\n", SS, MOSI, MISO, SCK);
  Serial.printf("I2C  SDA=%d  SCL=%d\n", SDA, SCL);
  Serial.println("=== done (repeats every 10 s) ===");
}

void loop() {
  delay(10000);
  Serial.println("(still alive)");
}
