// rf95_reliable_datagram_server.pde
#include <RHReliableDatagram.h>
#include <RH_RF95.h>
#include <SPI.h>

#define CLIENT_ADDRESS 1
#define SERVER_ADDRESS 2

// ✅ FIX 1: Define the correct pins for the Feather 32u4
#define RFM95_CS  8
#define RFM95_INT 7
#define RFM95_RST 4

// ✅ FIX 2: Must match the frequency defined in the client!
#define RF95_FREQ 915.0   // or 434.0 — must be identical on both boards

// ✅ FIX 3: Pass CS and INT pins to the driver
RH_RF95 driver(RFM95_CS, RFM95_INT);

RHReliableDatagram manager(driver, SERVER_ADDRESS);

void setup()
{
  // ✅ FIX 4: Manually reset the radio before init
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  Serial.begin(9600);
  while (!Serial);

  if (!manager.init())
    Serial.println("init failed");

  // ✅ FIX 5: Set frequency explicitly — must match client
  if (!driver.setFrequency(RF95_FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }

  // ✅ FIX 6: Set TX power using PA_BOOST pin (correct for Feather)
  driver.setTxPower(20, false);

  Serial.println("Server ready");
}

uint8_t data[] = "And hello back to you";
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];

void loop()
{
  if (manager.available())
  {
    uint8_t len = sizeof(buf);
    uint8_t from;
    if (manager.recvfromAck(buf, &len, &from))
    {
      Serial.print("got request from : 0x");
      Serial.print(from, HEX);
      Serial.print(": ");
      Serial.println((char*)buf);

      if (!manager.sendtoWait(data, sizeof(data), from))
        Serial.println("sendtoWait failed");
    }
  }
}