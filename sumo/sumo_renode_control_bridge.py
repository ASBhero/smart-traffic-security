import traci
import socket
import time

HOST = "127.0.0.1"
PORT = 25000   # نفس البورت بتاع ECU server أو Renode socket

# Connect to ECU / Renode / FOTA Client
sock = socket.create_connection((HOST, PORT))
print("Connected to ECU / Renode / FOTA Client")

# Start SUMO
traci.start([
    "sumo-gui",
    "-c",
    "traffic.sumocfg"
])

tl_id = "J5"
step = 0

while step < 300:
    traci.simulationStep()

    # 1) Read traffic data from SUMO
    north_south = (
        traci.lane.getLastStepVehicleNumber("-E1_0") +
        traci.lane.getLastStepVehicleNumber("-E2_0")
    )

    east_west = (
        traci.lane.getLastStepVehicleNumber("-E0_0") +
        traci.lane.getLastStepVehicleNumber("E0_0")
    )

    # 2) Build request signals
    pedestrian_request = 0
    emergency_request = 0

    # Simulated firmware version:
    # FW=1 before FOTA
    # FW=2 after FOTA
    firmware_version = 1

    if step >= 150:
        firmware_version = 2

    # Simulate pedestrian request before FOTA
    if step == 50:
        pedestrian_request = 1

    # Simulate emergency vehicle request after FOTA
    if step == 170:
        emergency_request = 1

    # 3) Send traffic data to ECU / FOTA Client / Controller
    msg = (
        f"NS={north_south};"
        f"EW={east_west};"
        f"PED={pedestrian_request};"
        f"EM={emergency_request};"
        f"FW={firmware_version}\n"
    )

    sock.sendall(msg.encode())
    print(f"Step={step} | Sent: {msg.strip()}")

    # 4) Receive decision from ECU / FOTA Client / Controller
    decision = sock.recv(1024).decode().strip()
    print("Received Decision:", decision)

    # 5) Apply decision to SUMO
    if decision == "NS_GREEN":
        traci.trafficlight.setPhase(tl_id, 2)
        applied_phase = 2

    elif decision == "EW_GREEN":
        traci.trafficlight.setPhase(tl_id, 0)
        applied_phase = 0

    elif decision == "PEDESTRIAN":
        traci.trafficlight.setPhase(tl_id, 1)
        applied_phase = 1

    elif decision == "EMERGENCY":
        traci.trafficlight.setPhase(tl_id, 3)
        applied_phase = 3

    elif decision == "SAFE_MODE":
        traci.trafficlight.setPhase(tl_id, 1)
        applied_phase = 1

    else:
        traci.trafficlight.setPhase(tl_id, 1)
        applied_phase = 1

    print("Applied Phase:", applied_phase)

    time.sleep(0.3)
    step += 1

input("Press Enter to close...")

sock.close()
traci.close()