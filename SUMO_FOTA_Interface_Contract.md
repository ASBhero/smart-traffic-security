# SUMO – FOTA Integration Interface Contract

## 1. Integration Scope

This interface connects the SUMO traffic simulation with the ECU logic and FOTA-enabled traffic controller.

The SUMO bridge sends traffic and event data to the ECU server.  
The ECU server applies traffic decision logic and FOTA feature availability, then returns the traffic light decision back to SUMO.

---

## 2. Data Flow

```text
SUMO
  ↓
sumo_renode_control_bridge.py
  ↓
Socket TCP Port 25000
  ↓
ecu_logic_server.py
  ↓
Decision
  ↓
SUMO Traffic Light Phase