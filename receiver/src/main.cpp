/*******************************************************************
 * File Name : receiver/src/main.cpp
 * Description : Draft code for receiver.
 * 
 * Author : Samuel McCollough and Nicholas Henricksen
 * Date Last Modified : 2/9/26
 * Referenced : https://github.com/UOP-Solarcar/systems-and-controls/blob/master/battery_protection/bps_fix/src/main.cpp
 *              https://registry.platformio.org/libraries/epsilonrt/RadioHead/examples/rf95/rf95_reliable_datagram_client/rf95_reliable_datagram_client.pde
 *******************************************************************/

#include <RH_RF95.h>
#include <SPI.h>

#define CLIENT_ADDRESS 1
#define SERVER_ADDRESS 2

// ── Feather 32u4 RFM95 hardwired pins ────────────────────────────────────────
#define RFM95_CS  8
#define RFM95_INT 7

// Singleton instance of the radio driver
RH_RF95 driver(RFM95_CS, RFM95_INT);

void setup() 
{
  Serial.begin(115200); while(!Serial){;}

  pinMode(RFM95_CS, OUTPUT);
  digitalWrite(RFM95_CS, HIGH);

  // ── LoRa init ───────────────────────────────────────────────────────────────
  Serial.print("LoRa init... ");
  if (!driver.init()) {
    Serial.println("FAILED - check RFM95 is seated properly on Feather");
    while (1);
  }
  Serial.println("OK");

  driver.setTxPower(20, false);
  driver.setCADTimeout(100);
  driver.setFrequency(915.0); // 915MHz for US, change to 868.0 for EU

  Serial.println("Ready.\n");
}

uint8_t data[73];
// Dont put this on the stack:
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
uint8_t len = 72;

void loop()
{
  if (driver.available())
  {
    if (driver.recv(buf, &len) && buf[0] == 0x4D);
    {
      Serial.write(&buf[1], len);
    }
  }
}