#include "Traffic_sm.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "esp_timer.h"

#include "hal_gpio.h"
#include "hal_uart.h"
#include "fota_manager.h"

#define RAPID_DOUBLE_PRESS_THRESHOLD_US   20000LL

typedef enum
{
    MODE_ALL_RED = 0,
    MODE_NORTH_GREEN,
    MODE_SOUTH_GREEN,
    MODE_EAST_GREEN,
    MODE_WEST_GREEN,
    MODE_PEDESTRIAN,
    MODE_SERVICE,
    MODE_EMERGENCY_NORTH
} TrafficMode_t;

typedef enum
{
    INPUT_NORTH = 0,
    INPUT_SOUTH,
    INPUT_EAST,
    INPUT_WEST,
    INPUT_PEDESTRIAN,
    INPUT_SERVICE,
    INPUT_EMERGENCY_NORTH,
    INPUT_COUNT
} TrafficInput_t;

static TrafficMode_t current_mode = MODE_ALL_RED;

static bool last_input_state[INPUT_COUNT] = {false};
static int64_t last_press_time_us[INPUT_COUNT] = {0};

static bool TrafficSM_IsNewPress(TrafficInput_t input_id, bool current_pressed)
{
    bool new_press = (current_pressed == true) && (last_input_state[input_id] == false);
    last_input_state[input_id] = current_pressed;

    return new_press;
}

static bool SecurityFilter_CheckInput(TrafficInput_t input_id, const char *input_name)
{
    int64_t now_us = esp_timer_get_time();
    int64_t previous_us = last_press_time_us[input_id];

    last_press_time_us[input_id] = now_us;

    if ((FOTA_Manager_IsAntiHackAppActive() == true) && (previous_us > 0))
    {
        int64_t delta_us = now_us - previous_us;

        if ((delta_us > 0) && (delta_us < RAPID_DOUBLE_PRESS_THRESHOLD_US))
        {
            char msg[160];

            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("SECURITY ALERT: Rapid double-press attack detected");

            snprintf(
                msg,
                sizeof(msg),
                "Rejected Input: %s | Delta Time: %lld us",
                input_name,
                (long long)delta_us
            );

            HAL_UART_SendLine(msg);
            HAL_UART_SendLine("Reason: Two presses detected with difference < 20 ms");
            HAL_UART_SendLine("Action: Switch command rejected");
            HAL_UART_SendLine("----------------------------------");

            return false;
        }
    }

    return true;
}

static void TrafficSM_SetMode(TrafficMode_t new_mode)
{
    if (current_mode == new_mode)
    {
        return;
    }

    current_mode = new_mode;

    switch (new_mode)
    {
        case MODE_ALL_RED:
            HAL_GPIO_ShowAllRed();
            HAL_UART_SendLine("STATE: ALL RED");
            HAL_UART_SendLine("Waiting for switch input...");
            break;

        case MODE_NORTH_GREEN:
            HAL_GPIO_ShowNorthGreen();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("North Switch Pressed: YES");
            HAL_UART_SendLine("Decision: North traffic signal is GREEN");
            HAL_UART_SendLine("North: GREEN | South/East/West: RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_SOUTH_GREEN:
            HAL_GPIO_ShowSouthGreen();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("South Switch Pressed: YES");
            HAL_UART_SendLine("Decision: South traffic signal is GREEN");
            HAL_UART_SendLine("South: GREEN | North/East/West: RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_EAST_GREEN:
            HAL_GPIO_ShowEastGreen();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("East Switch Pressed: YES");
            HAL_UART_SendLine("Decision: East traffic signal is GREEN");
            HAL_UART_SendLine("East: GREEN | North/South/West: RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_WEST_GREEN:
            HAL_GPIO_ShowWestGreen();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("West Switch Pressed: YES");
            HAL_UART_SendLine("Decision: West traffic signal is GREEN");
            HAL_UART_SendLine("West: GREEN | North/South/East: RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_PEDESTRIAN:
            HAL_GPIO_ShowPedestrianCrossing();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("Pedestrian Request: YES");
            HAL_UART_SendLine("Decision: Stop all vehicles for pedestrian crossing");
            HAL_UART_SendLine("Traffic State: ALL SIGNALS RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_SERVICE:
            HAL_GPIO_ShowServiceSafeMode();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("Service Switch Activated: YES");
            HAL_UART_SendLine("Decision: Enter service safe mode");
            HAL_UART_SendLine("Traffic State: ALL SIGNALS RED");
            HAL_UART_SendLine("----------------------------------");
            break;

        case MODE_EMERGENCY_NORTH:
            HAL_GPIO_ShowEmergencyNorthOnly();
            HAL_UART_SendLine("----------------------------------");
            HAL_UART_SendLine("NORTH EMERGENCY SWITCH PRESSED");
            HAL_UART_SendLine("Emergency Vehicle Condition: TRUE");
            HAL_UART_SendLine("Decision: Emergency override activated");
            HAL_UART_SendLine("North Direction: OPEN / GREEN");
            HAL_UART_SendLine("South Direction: CLOSED / RED");
            HAL_UART_SendLine("East Direction : CLOSED / RED");
            HAL_UART_SendLine("West Direction : CLOSED / RED");
            HAL_UART_SendLine("Broadcast: Emergency vehicle alert sent to all sides");
            HAL_UART_SendLine("----------------------------------");
            break;

        default:
            HAL_GPIO_ShowAllRed();
            HAL_UART_SendLine("ERROR: Unknown traffic mode");
            break;
    }
}

void TrafficSM_Init(void)
{
    current_mode = MODE_ALL_RED;

    for (int i = 0; i < INPUT_COUNT; i++)
    {
        last_input_state[i] = false;
        last_press_time_us[i] = 0;
    }

    HAL_UART_SendLine("Traffic State Machine Initialized");
    HAL_GPIO_ShowAllRed();
    HAL_UART_SendLine("STATE: ALL RED");
    HAL_UART_SendLine("Press any switch to control the intersection.");
}

void TrafficSM_Run(void)
{
    bool emergency_pressed = HAL_GPIO_IsNorthEmergencySwitchPressed();

    bool service_pressed = HAL_GPIO_IsServiceSwitchActivated();
    bool pedestrian_pressed = HAL_GPIO_IsPedestrianRequested();

    bool north_pressed = HAL_GPIO_IsNorthSwitchPressed();
    bool south_pressed = HAL_GPIO_IsSouthSwitchPressed();
    bool east_pressed = HAL_GPIO_IsEastSwitchPressed();
    bool west_pressed = HAL_GPIO_IsWestSwitchPressed();

    bool emergency_new_press = TrafficSM_IsNewPress(INPUT_EMERGENCY_NORTH, emergency_pressed);
    bool service_new_press = TrafficSM_IsNewPress(INPUT_SERVICE, service_pressed);
    bool pedestrian_new_press = TrafficSM_IsNewPress(INPUT_PEDESTRIAN, pedestrian_pressed);
    bool north_new_press = TrafficSM_IsNewPress(INPUT_NORTH, north_pressed);
    bool south_new_press = TrafficSM_IsNewPress(INPUT_SOUTH, south_pressed);
    bool east_new_press = TrafficSM_IsNewPress(INPUT_EAST, east_pressed);
    bool west_new_press = TrafficSM_IsNewPress(INPUT_WEST, west_pressed);

    // Highest priority: North Emergency Override
    if (emergency_pressed)
    {
        if (emergency_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_EMERGENCY_NORTH, "North Emergency Switch") == true)
            {
                TrafficSM_SetMode(MODE_EMERGENCY_NORTH);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_EMERGENCY_NORTH);
        }

        return;
    }

    // Service switch triggers FOTA
    if (service_pressed)
    {
        if (service_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_SERVICE, "Service Switch") == true)
            {
                FOTA_Manager_InstallNewApplication();
                TrafficSM_SetMode(MODE_SERVICE);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_SERVICE);
        }

        return;
    }

    if (pedestrian_pressed)
    {
        if (pedestrian_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_PEDESTRIAN, "Pedestrian Request") == true)
            {
                TrafficSM_SetMode(MODE_PEDESTRIAN);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_PEDESTRIAN);
        }

        return;
    }

    if (north_pressed)
    {
        if (north_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_NORTH, "North Switch") == true)
            {
                TrafficSM_SetMode(MODE_NORTH_GREEN);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_NORTH_GREEN);
        }

        return;
    }

    if (south_pressed)
    {
        if (south_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_SOUTH, "South Switch") == true)
            {
                TrafficSM_SetMode(MODE_SOUTH_GREEN);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_SOUTH_GREEN);
        }

        return;
    }

    if (east_pressed)
    {
        if (east_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_EAST, "East Switch") == true)
            {
                TrafficSM_SetMode(MODE_EAST_GREEN);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_EAST_GREEN);
        }

        return;
    }

    if (west_pressed)
    {
        if (west_new_press)
        {
            if (SecurityFilter_CheckInput(INPUT_WEST, "West Switch") == true)
            {
                TrafficSM_SetMode(MODE_WEST_GREEN);
            }
        }
        else
        {
            TrafficSM_SetMode(MODE_WEST_GREEN);
        }

        return;
    }

    TrafficSM_SetMode(MODE_ALL_RED);
}