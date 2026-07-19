@echo off
title Smart Traffic Closed Loop Runner

echo Starting ECU Logic Server...
start "ECU Logic Server" cmd /k python ecu_logic_server.py

timeout /t 3

echo Starting SUMO Closed Loop Bridge...
start "SUMO Closed Loop Bridge" cmd /k python sumo_renode_control_bridge.py

pause