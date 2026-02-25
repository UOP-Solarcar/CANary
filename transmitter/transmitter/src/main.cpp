/*******************************************************************
 * File Name : transmitter/src/main.cpp
 * Description : Draft code for transmitter.
 * 
 * Author : Samuel McCollough and Nicholas Henricksen
 * Date Last Modified : 2/4/26
 * Referenced : https://github.com/UOP-Solarcar/systems-and-controls/blob/master/battery_protection/bps_fix/src/main.cpp
 *              https://registry.platformio.org/libraries/epsilonrt/RadioHead/examples/rf95/rf95_reliable_datagram_client/rf95_reliable_datagram_client.pde
 *******************************************************************/

#include <RHReliableDatagram.h>
#include <RH_RF95.h>
#include <mcp2515.h>
#include <SPI.h>

#define CLIENT_ADDRESS 1
#define SERVER_ADDRESS 2

// ── Feather 32u4 RFM95 hardwired pins ────────────────────────────────────────
#define RFM95_CS  8
#define RFM95_INT 7

// ── MCP2515 CS pin ────────────────────────────────────────────────────────────
#define MCP2515_CS 6

// ── Object instances ──────────────────────────────────────────────────────────
MCP2515 mcp2515(MCP2515_CS);
RH_RF95 driver(RFM95_CS, RFM95_INT);
RHReliableDatagram manager(driver, CLIENT_ADDRESS);

void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("Booting...");

  // Pull both CS pins HIGH before SPI init to prevent bus contention
  pinMode(MCP2515_CS, OUTPUT);
  digitalWrite(MCP2515_CS, HIGH);
  pinMode(RFM95_CS, OUTPUT);
  digitalWrite(RFM95_CS, HIGH);

  SPI.begin();

  // ── CAN init ────────────────────────────────────────────────────────────────
  Serial.print("CAN init... ");
  mcp2515.reset();
  if (mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ) == MCP2515::ERROR_OK) {
    Serial.println("OK");
  } else {
    Serial.println("FAILED - check MCP2515 wiring, and use MCP_16MHZ if crystal is 16MHz");
  }
  mcp2515.setListenOnlyMode();

  // ── LoRa init ───────────────────────────────────────────────────────────────
  Serial.print("LoRa init... ");
  if (!manager.init()) {
    Serial.println("FAILED - check RFM95 is seated properly on Feather");
    while (1);
  }
  Serial.println("OK");

  driver.setTxPower(20, false);
  driver.setCADTimeout(100);
  driver.setFrequency(915.0); // 915MHz for US, change to 868.0 for EU

  Serial.println("Ready.\n");
}

uint8_t data[12];
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];

void loop() {
  can_frame f;
  while (mcp2515.readMessage(&f) == MCP2515::ERROR_OK) {
    Serial.print("CAN RX ID: 0x");
    Serial.print(f.can_id, HEX);
    Serial.print(" -> Sending over LoRa... ");

    // Pack CAN ID (4 bytes) + CAN data (8 bytes) = 12 bytes total
    data[0] = (f.can_id >> 24) & 0xFF;
    data[1] = (f.can_id >> 16) & 0xFF;
    data[2] = (f.can_id >> 8)  & 0xFF;
    data[3] =  f.can_id        & 0xFF;
    memcpy(&data[4], f.data, 8);

    if (manager.sendtoWait(data, sizeof(data), SERVER_ADDRESS)) {
      Serial.println("OK");
    } else {
      Serial.println("sendtoWait failed");
    }
  }
}