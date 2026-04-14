/*******************************************************************
 * File Name : transmitter/src/main.cpp
 * Description : Draft code for transmitter.
 * 
 * Author : Samuel McCollough and Nicholas Henricksen
 * Date Last Modified : 2/4/26
 * Referenced : https://github.com/UOP-Solarcar/systems-and-controls/blob/master/battery_protection/bps_fix/src/main.cpp
 *              https://registry.platformio.org/libraries/epsilonrt/RadioHead/examples/rf95/rf95_reliable_datagram_client/rf95_reliable_datagram_client.pde
 *******************************************************************/

#include <RH_RF95.h>
#include <mcp2515.h>
#include <SPI.h>
#include <can.h>

//Feather 32u4 RFM95 hardwired pins
#define RFM95_CS  8
#define RFM95_INT 7

//MCP2515 CS pin
#define MCP2515_CS 6

const canid_t IDS[] = {0x6B0, 0x6B1, 0x6B2, 0x6B3, 0x6B4, 0x36};
const uint8_t length = sizeof(IDS)/ sizeof(IDS[0]);

uint8_t data[length*12 + 1];
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
uint8_t count = 0;
bool id_check[length] = {false};

//Object instances
MCP2515 mcp2515(MCP2515_CS);
RH_RF95 driver(RFM95_CS, RFM95_INT);

void setup() {
  Serial.begin(115200);
  Serial.println("Booting...");

  // Pull both CS pins HIGH before SPI init to prevent bus contention
  pinMode(MCP2515_CS, OUTPUT);
  digitalWrite(MCP2515_CS, HIGH);
  pinMode(RFM95_CS, OUTPUT);
  digitalWrite(RFM95_CS, HIGH);

  SPI.begin();

  //CAN init
  Serial.print("CAN init... ");
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setFilterMask(MCP2515::MASK0, false, 0x00000000); // accept all
  mcp2515.setFilterMask(MCP2515::MASK1, false, 0x00000000); // accept all
  mcp2515.setNormalMode();

  //LoRa init
  Serial.print("LoRa init... ");
  if (!driver.init()) {
    Serial.println("FAILED");
    while (1);
  }
  Serial.println("OK");

  driver.setTxPower(20, false);
  driver.setCADTimeout(100);
  driver.setFrequency(915.0); // 915MHz for US
  
  Serial.println("Ready.\n");
}

void loop() {
  can_frame f;
  while (mcp2515.readMessage(&f) == MCP2515::ERROR_OK) {
    for (int i = 0; i < length; i++) {
      if (!id_check[i] && IDS[i] == f.can_id) {
        data[(i*12) + 1] = (f.can_id >> 24) & 0xFF;
        data[(i*12) + 2] = (f.can_id >> 16) & 0xFF;
        data[(i*12) + 3] = (f.can_id >> 8)  & 0xFF;
        data[(i*12) + 4] =  f.can_id        & 0xFF;
        memcpy(&data[(i*12) + 5], f.data, 8);
        id_check[i] = true;
        count = (count + 1);
      }
    }
    if (count == length) count = 0;
    else continue;

    // Pack CAN ID (4 bytes) + CAN data (8 bytes) = 12 bytes total
    for (int i = 0; i < length; i++) id_check[i] = false;
    data[0] = 0x4D;

    if (driver.send(data, sizeof(data))) {
      Serial.println("OK");
    } else {
      Serial.println("send failed");
    }
  }
}