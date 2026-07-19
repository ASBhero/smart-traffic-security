#include "hal_gpio.h"

#include "driver/gpio.h"

// ===============================
// North traffic signal
// ===============================
#define N_RED       GPIO_NUM_4
#define N_YELLOW    GPIO_NUM_5
#define N_GREEN     GPIO_NUM_6

// ===============================
// South traffic signal
// ===============================
#define S_RED       GPIO_NUM_17
#define S_YELLOW    GPIO_NUM_18
#define S_GREEN     GPIO_NUM_8

// ===============================
// East traffic signal
// ===============================
#define E_RED       GPIO_NUM_7
#define E_YELLOW    GPIO_NUM_15
#define E_GREEN     GPIO_NUM_16

// ===============================
// West traffic signal
// ===============================
#define W_RED       GPIO_NUM_12
#define W_YELLOW    GPIO_NUM_13
#define W_GREEN     GPIO_NUM_14

// ===============================
// Switches / requests
// ===============================
#define NORTH_SWITCH        GPIO_NUM_10
#define SOUTH_SWITCH        GPIO_NUM_11
#define EAST_SWITCH         GPIO_NUM_35
#define WEST_SWITCH         GPIO_NUM_36
#define PED_REQUEST         GPIO_NUM_37
#define SERVICE_SWITCH      GPIO_NUM_38
#define NORTH_EMERGENCY     GPIO_NUM_39

static void set_led(gpio_num_t pin, int level)
{
    gpio_set_level(pin, level);
}

static void all_lights_off(void)
{
    set_led(N_RED, 0);
    set_led(N_YELLOW, 0);
    set_led(N_GREEN, 0);

    set_led(S_RED, 0);
    set_led(S_YELLOW, 0);
    set_led(S_GREEN, 0);

    set_led(E_RED, 0);
    set_led(E_YELLOW, 0);
    set_led(E_GREEN, 0);

    set_led(W_RED, 0);
    set_led(W_YELLOW, 0);
    set_led(W_GREEN, 0);
}

void HAL_GPIO_Init(void)
{
    gpio_config_t led_config = {
        .pin_bit_mask =
            (1ULL << N_RED) |
            (1ULL << N_YELLOW) |
            (1ULL << N_GREEN) |
            (1ULL << S_RED) |
            (1ULL << S_YELLOW) |
            (1ULL << S_GREEN) |
            (1ULL << E_RED) |
            (1ULL << E_YELLOW) |
            (1ULL << E_GREEN) |
            (1ULL << W_RED) |
            (1ULL << W_YELLOW) |
            (1ULL << W_GREEN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    gpio_config(&led_config);

    gpio_config_t input_config = {
        .pin_bit_mask =
            (1ULL << NORTH_SWITCH) |
            (1ULL << SOUTH_SWITCH) |
            (1ULL << EAST_SWITCH) |
            (1ULL << WEST_SWITCH) |
            (1ULL << PED_REQUEST) |
            (1ULL << SERVICE_SWITCH) |
            (1ULL << NORTH_EMERGENCY),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };

    gpio_config(&input_config);

    HAL_GPIO_ShowAllRed();
}

void HAL_GPIO_ShowAllRed(void)
{
    all_lights_off();

    set_led(N_RED, 1);
    set_led(S_RED, 1);
    set_led(E_RED, 1);
    set_led(W_RED, 1);
}

void HAL_GPIO_ShowNorthGreen(void)
{
    all_lights_off();

    set_led(N_GREEN, 1);

    set_led(S_RED, 1);
    set_led(E_RED, 1);
    set_led(W_RED, 1);
}

void HAL_GPIO_ShowSouthGreen(void)
{
    all_lights_off();

    set_led(S_GREEN, 1);

    set_led(N_RED, 1);
    set_led(E_RED, 1);
    set_led(W_RED, 1);
}

void HAL_GPIO_ShowEastGreen(void)
{
    all_lights_off();

    set_led(E_GREEN, 1);

    set_led(N_RED, 1);
    set_led(S_RED, 1);
    set_led(W_RED, 1);
}

void HAL_GPIO_ShowWestGreen(void)
{
    all_lights_off();

    set_led(W_GREEN, 1);

    set_led(N_RED, 1);
    set_led(S_RED, 1);
    set_led(E_RED, 1);
}

void HAL_GPIO_ShowPedestrianCrossing(void)
{
    HAL_GPIO_ShowAllRed();
}

void HAL_GPIO_ShowServiceSafeMode(void)
{
    HAL_GPIO_ShowAllRed();
}

void HAL_GPIO_ShowEmergencyNorthOnly(void)
{
    HAL_GPIO_ShowNorthGreen();
}

bool HAL_GPIO_IsNorthSwitchPressed(void)
{
    return gpio_get_level(NORTH_SWITCH) == 0;
}

bool HAL_GPIO_IsSouthSwitchPressed(void)
{
    return gpio_get_level(SOUTH_SWITCH) == 0;
}

bool HAL_GPIO_IsEastSwitchPressed(void)
{
    return gpio_get_level(EAST_SWITCH) == 0;
}

bool HAL_GPIO_IsWestSwitchPressed(void)
{
    return gpio_get_level(WEST_SWITCH) == 0;
}

bool HAL_GPIO_IsPedestrianRequested(void)
{
    return gpio_get_level(PED_REQUEST) == 0;
}

bool HAL_GPIO_IsServiceSwitchActivated(void)
{
    return gpio_get_level(SERVICE_SWITCH) == 0;
}

bool HAL_GPIO_IsNorthEmergencySwitchPressed(void)
{
    return gpio_get_level(NORTH_EMERGENCY) == 0;
}