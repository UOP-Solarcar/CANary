/*******************************************************************
 * File Name : transmitter/src/main.cpp
 * Description : Draft code for transmitter.
 * 
 * Author : Samuel McCollough and Nicholas Henricksen
 * Date Last Modified : 2/4/26
 * Referenced : https://github.com/UOP-Solarcar/systems-and-controls/blob/master/battery_protection/bps_fix/src/main.cpp
 *              https://registry.platformio.org/libraries/epsilonrt/RadioHead/examples/rf95/rf95_reliable_datagram_client/rf95_reliable_datagram_client.pde
 *******************************************************************/

/*
Idea: Messages stored into buffer, should represent all IDS. Send transmission with all IDS as one packet.
*/
#include <RH_RF95.h>
#include <mcp2515.h>
#include <SPI.h>
#include <can.h>

//Feather 32u4 RFM95 hardwired pins
#define RFM95_CS  8
#define RFM95_INT 7

//MCP2515 CS pin
#define MCP2515_CS 6
/*
//interrupt setup
volatile bool canInterrupt = false;

void canISR() {
  canInterrupt = true;
}

#define CAN_QUEUE_SIZE 16

can_frame canQueue[CAN_QUEUE_SIZE];
volatile uint8_t head = 0;
volatile uint8_t tail = 0;
*/
const canid_t IDS[] = {0x6B0, 0x6B1, 0x6B2, 0x6B3, 0x6B4};

uint8_t data[61];
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
uint8_t length = sizeof(IDS)/ sizeof(IDS[0]);
uint8_t count = 0;

//Object instances
MCP2515 mcp2515(MCP2515_CS);
RH_RF95 driver(RFM95_CS, RFM95_INT);

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

  //CAN init
  Serial.print("CAN init... ");
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setFilterMask(MCP2515::MASK0, false, 0x00000000); // accept all
  mcp2515.setFilterMask(MCP2515::MASK1, false, 0x00000000); // accept all
  mcp2515.setNormalMode();
  //mcp2515.setRegister(MCP2515::REGISTER::MCP_CANINTE, 0x03); // Enable RX0IE and RX1IE

  //LoRa init
  Serial.print("LoRa init... ");
  if (!driver.init()) {
    Serial.println("FAILED");
    while (1);
  }
  Serial.println("OK");

  driver.setTxPower(20, false);
  driver.setCADTimeout(100);
  driver.setFrequency(915.0); // 915MHz for US, change to 868.0 for EU
  /*
  // Drain any messages already sitting in the buffer
  can_frame dummy;
  while (mcp2515.readMessage(&dummy) == MCP2515::ERROR_OK) {}

  pinMode(3, INPUT_PULLUP);//pin 3 is interrupt pin
  attachInterrupt(0, canISR, FALLING);//interrupt 0 is mapped to pin 3*/
  Serial.println("Ready.\n");
}

void loop() {/*
  if (canInterrupt) {
    canInterrupt = false;
    Serial.println("ISR fired!");
    
    can_frame f;
    uint8_t count = 0;
    while (count < 4 && mcp2515.readMessage(&f) == MCP2515::ERROR_OK) {
      uint8_t next = (head + 1) % CAN_QUEUE_SIZE;
      if (next != tail) {
        canQueue[head] = f;
        head = next;
      }
      count++;
      if(count == 4) canInterrupt = true;
    }
  }

  if (tail != head) {
    can_frame &f = canQueue[tail];

    Serial.print("CAN RX ID: 0x");
    Serial.println(f.can_id, HEX);

    data[0] = (f.can_id >> 24) & 0xFF;
    data[1] = (f.can_id >> 16) & 0xFF;
    data[2] = (f.can_id >> 8) & 0xFF;
    data[3] = f.can_id & 0xFF;
    memcpy(&data[4], f.data, 8);

    manager.sendtoWait(data, sizeof(data), SERVER_ADDRESS);

    tail = (tail + 1) % CAN_QUEUE_SIZE;
  }

  */
  can_frame f;
  while (mcp2515.readMessage(&f) == MCP2515::ERROR_OK) {
    if (f.can_id == IDS[count]) {
      data[(count*12) + 1] = (f.can_id >> 24) & 0xFF;
      data[(count*12) + 2] = (f.can_id >> 16) & 0xFF;
      data[(count*12) + 3] = (f.can_id >> 8)  & 0xFF;
      data[(count*12) + 4] =  f.can_id        & 0xFF;
      memcpy(&data[(count*12) + 5], f.data, 8);
      count = (count + 1);
      if (count == length) count = 0;
      else continue;
    } else continue;
    /*Serial.print("CAN RX ID: 0x");
    Serial.print(f.can_id, HEX);
    Serial.print(" -> Sending over LoRa... ");*/

    // Pack CAN ID (4 bytes) + CAN data (8 bytes) = 12 bytes total
    data[0] = 0x4D;

    if (driver.send(data, sizeof(data))) {
      Serial.println("OK");
    } else {
      Serial.println("send failed");
    }
    count = (count + 1) % length;
  }
}