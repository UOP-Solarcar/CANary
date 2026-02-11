#include <Arduino.h>

int i;

void setup() {
  i = 0;
}

void loop() {
  i++;
  Serial.println(i);
}
