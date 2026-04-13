# CANary

**CANary** is a real-time telemetry pipeline for remotely monitoring Controller Area Network (CAN) data. It ingests CAN frames from a Battery Management System (BMS), transmits them over RF, and visualizes the data live via a Streamlit dashboard.

---

## Architecture Overview

The system is composed of embedded and host-side components that form a continuous data pipeline:

1. **CAN Ingestion (Embedded)**  
   CAN frames are read from the BMS using the `mcp2515` controller.

2. **RF Transmission (Embedded)**  
   Each CAN frame is parsed into:
   - Message ID  
   - Data payload  
   These are transmitted wirelessly using the `RH_RF95` (LoRa) library.

3. **RF Reception (Embedded)**  
   The receiver reconstructs the CAN frame from the RF packet and forwards it over serial to the host system.

4. **Data Logging (Host)**  
   Incoming data is parsed and written to a `.csv` file in real time for persistence and analysis.

5. **Visualization (Host)**  
   A Streamlit dashboard reads the live dataset and updates visualizations dynamically.

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/UOP-Solarcar/CANary.git
cd CANary

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Compile and upload program to connected transmitter
pio run -t upload transmitter\main.cpp

# 4. Compile and upload receiver program to connected receiver
pio run -t upload receiver\main.cpp

# 5. Run the Serial Receiver
cd application
python serialRcv.py

# 6. Run the Streamlit dashboard
streamlit run dashboard.py