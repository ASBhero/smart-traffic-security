import traci

traci.start(["sumo-gui", "-c", "traffic.sumocfg"])

tl_id = "J5"

print("Current state:", traci.trafficlight.getRedYellowGreenState(tl_id))

logic = traci.trafficlight.getAllProgramLogics(tl_id)[0]

print("Number of phases:", len(logic.phases))

for i, phase in enumerate(logic.phases):
    print(f"Phase {i}: duration={phase.duration}, state={phase.state}")

print("\nControlled lanes:")
for lane in traci.trafficlight.getControlledLanes(tl_id):
    print(lane)

traci.close()