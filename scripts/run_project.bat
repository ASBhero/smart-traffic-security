@echo off
title Smart Traffic SUMO-FOTA Integration

cd /d "%~dp0"

echo ================================
echo Smart Traffic SUMO-FOTA Demo
echo ================================

if not exist firmware_status.txt (
    echo 1> firmware_status.txt
    echo Created firmware_status.txt = 1
) else (
    echo firmware_status.txt found
)

echo.
echo Starting ECU Logic Server...
start "ECU Logic Server" cmd /k python ecu_logic_server.py

timeout /t 3 > nul

echo.
echo Starting SUMO Bridge...
start "SUMO Bridge" cmd /k python sumo_renode_control_bridge.py

echo.
echo Demo started successfully.
echo.
echo To simulate FOTA update:
echo Open firmware_status.txt and change 1 to 2
echo Then save the file.
echo.
pause