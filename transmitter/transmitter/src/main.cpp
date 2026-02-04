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

// Singleton instance of the radio driver
RH_RF95 driver;

// Class to manage message delivery and receipt, using the driver declared above
RHReliableDatagram manager(driver, CLIENT_ADDRESS);


void setup() 
{

  Serial.begin(115200); while(!Serial){;}

  //CAN Module Config
  SPI.begin();
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setNormalMode();

  //Radio Config
  if (!manager.init())
    Serial.println("init failed");
  driver.setTxPower(20, false);
  driver.setCADTimeout(100);
}

char data[8];
// Dont put this on the stack:
uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];

void loop()
{
  can_frame f;
  while (mcp2515.readMessage(&f) == MCP2515::ERROR_OK) {
    Serial.println("Sending to rf95_reliable_datagram_server");
    
    data = f.can_id + f.data;
    // Send a message to manager_server
    if (!manager.sendtoWait(data, sizeof(data), SERVER_ADDRESS)) Serial.println("sendtoWait failed");  
  }  
}