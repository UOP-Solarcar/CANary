#include <Arduino.h>

uint8_t msg[12];

void setup() {
  Serial.begin(115200);
  msg[0] = 0x00;
  msg[1] = 0x00;
  msg[2] = 0x06;
  msg[3] = 0xB0;
  msg[4] = 0xD8;
  msg[5] = 0x03;
  msg[6] = 0xB6;
  msg[7] = 0x4E;
  msg[8] = 0x4B;
  msg[9] = 0x00;
  msg[10] = 0x03;
  msg[11] = 0xA1;
}

void loop() {
  for (int i = 0; i < 12; ++i) {
     Serial.write(msg, 12);
  }
}
