#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "hal_uart.h"
#include "hal_gpio.h"
#include "fota_manager.h"
#include "Traffic_sm.h"

void app_main(void)
{
    HAL_UART_Init();
    HAL_GPIO_Init();
    FOTA_Manager_Init();

    HAL_UART_SendLine("==================================");
    HAL_UART_SendLine("Smart Traffic System Started");
    HAL_UART_SendLine("Controller: ESP32-S3");
    HAL_UART_SendLine("Environment: Wokwi Simulator");
    HAL_UART_SendLine("Architecture: TrafficSM + HAL + FOTA + Secure Boot");
    HAL_UART_SendLine("Secure IC: Microchip ATECC608 Secure Element");
    HAL_UART_SendLine("Secure External Flash: Backup / Rollback Storage");
    HAL_UART_SendLine("Emergency: North Emergency Override");
    HAL_UART_SendLine("FOTA: Press Service Switch to install SW_APP_V2_ANTI_HACK");
    HAL_UART_SendLine("Security Rule After FOTA: Reject switch double-press < 20 ms");
    HAL_UART_SendLine("==================================");

    TrafficSM_Init();

    while (1)
    {
        TrafficSM_Run();

        /*
         * 1 ms loop is used to support fast input monitoring
         * and the anti-hack double-press timing rule.
         */
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}