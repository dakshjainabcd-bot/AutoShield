// AutoShield Phase 0 - hello_serial
// Prints one line per second so you can prove upload + Serial Monitor work.
// Serial Monitor must be set to 115200 baud.

void setup() {
  Serial.begin(115200);
  delay(2000);  // gives the USB serial link time to appear
  Serial.println("AutoShield hello_serial started");
}

void loop() {
  Serial.print("Hello from ");
  Serial.print(ESP.getChipModel());   // tells you which board this is
  Serial.print(" | uptime ms: ");
  Serial.println(millis());
  delay(1000);
}
