#include <Arduino.h>

int i;

void setup() {
  i = 0;
  Serial.begin(115200);
}

void loop() {
  i++;
  Serial.println(i);
}
