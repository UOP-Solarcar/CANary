#include <RHReliableDatagram.h>
#include <RH_RF95.h>
#include <SPI.h>

#define CLIENT_ADDRESS 1
#define SERVER_ADDRESS 2

// ✅ FIX 1: Define the correct pins for the Feather 32u4
#define RFM95_CS  8
#define RFM95_INT 7
#define RFM95_RST 4

// ✅ FIX 2: Set your frequency — must match the server!
#define RF95_FREQ 915.0   // or 434.0 depending on your module

// ✅ FIX 3: Pass CS and INT pins to the driver
RH_RF95 driver(RFM95_CS, RFM95_INT);

RHReliableDatagram manager(driver, CLIENT_ADDRESS);

void setup()
{
  // ✅ FIX 4: Manually reset the radio — required on Feather 32u4
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);

  Serial.begin(9600);
  while (!Serial);  // Note: remove this line if running without USB connected

  if (!manager.init())
    Serial.println("init failed");

  // ✅ FIX 5: Set frequency explicitly
  if (!driver.setFrequency(RF95_FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }

  // ✅ FIX 6: Set TX power (Feather uses PA_BOOST pin)
  driver.setTxPower(20, false);

  Serial.println("Client ready");
}

uint8_t data[] = "Hello World!";
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];

void loop()
{
  Serial.println("Sending to rf95_reliable_datagram_server");

  if (manager.sendtoWait(data, sizeof(data), SERVER_ADDRESS))
  {
    uint8_t len = sizeof(buf);
    uint8_t from;
    if (manager.recvfromAckTimeout(buf, &len, 2000, &from))
    {
      Serial.print("got reply from : 0x");
      Serial.print(from, HEX);
      Serial.print(": ");
      Serial.println((char*)buf);
    }
    else
    {
      Serial.println("No reply, is rf95_reliable_datagram_server running?");
    }
  }
  else
    Serial.println("sendtoWait failed");

  delay(500);
}