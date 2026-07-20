import traci
import socket
import time

HOST = "127.0.0.1"
PORT = 25000

# الاتصال بـ Renode
sock = socket.create_connection((HOST, PORT))

print("Connected to Renode")

# تشغيل SUMO
traci.start([
    "sumo-gui",
    "-c",
    "traffic.sumocfg"
])

tl_id = "J5"

step = 0

while step < 300:

    traci.simulationStep()

    # قراءة traffic density
    north_south = (
        traci.lane.getLastStepVehicleNumber("-E1_0") +
        traci.lane.getLastStepVehicleNumber("-E2_0")
    )

    east_west = (
        traci.lane.getLastStepVehicleNumber("-E0_0") +
        traci.lane.getLastStepVehicleNumber("E0_0")
    )

    # إرسال البيانات إلى Renode
    msg = f"NS={north_south};EW={east_west}\n"

    print("Sending:", msg.strip())

    sock.sendall(msg.encode())

    time.sleep(0.3)

    step += 1

input("Press Enter to close...")

sock.close()
traci.close()