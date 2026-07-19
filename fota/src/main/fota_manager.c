#include "fota_manager.h"

#include <stdbool.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "hal_uart.h"
#include "secure_boot_manager.h"
#include "backup_manager.h"

typedef enum
{
    SW_APP_V1_BASIC = 0,
    SW_APP_V2_ANTI_HACK
} SW_AppVersion_t;

typedef struct
{
    const char *name;
    uint32_t version;
    const char *hash;
} FirmwareImage_t;

static SW_AppVersion_t active_app = SW_APP_V1_BASIC;
static uint32_t active_version = 1U;

static const FirmwareImage_t current_firmware_v1 = {
    .name = "SW_APP_V1_BASIC",
    .version = 1U,
    .hash = "HASH_SW_APP_V1_BASIC"
};

static const FirmwareImage_t cloud_firmware_v2 = {
    .name = "SW_APP_V2_ANTI_HACK",
    .version = 2U,
    .hash = "HASH_SW_APP_V2_ANTI_HACK_CLOUD_SIGNED"
};

/*
 * This represents the image after installation.
 * To simulate a hacked/tampered update, change this hash to a different value.
 */
static const FirmwareImage_t installed_firmware_v2 = {
    .name = "SW_APP_V2_ANTI_HACK",
    .version = 2U,
    .hash = "HASH_SW_APP_V2_ANTI_HACK_CLOUD_SIGNED"
};

void FOTA_Manager_Init(void)
{
    active_app = SW_APP_V1_BASIC;
    active_version = current_firmware_v1.version;

    SecureBoot_Manager_Init();
    BackupManager_Init();

    HAL_UART_SendLine("FOTA Manager Initialized");
    HAL_UART_SendLine("Active SW Application: SW_APP_V1_BASIC");
    HAL_UART_SendLine("FOTA State: Waiting for Service Switch");
}

void FOTA_Manager_InstallNewApplication(void)
{
    if (active_app == SW_APP_V2_ANTI_HACK)
    {
        HAL_UART_SendLine("FOTA: SW_APP_V2_ANTI_HACK is already installed");
        return;
    }

    HAL_UART_SendLine("----------------------------------");
    HAL_UART_SendLine("FOTA REQUEST RECEIVED");
    HAL_UART_SendLine("Trigger Source: Service / Maintenance Switch");
    HAL_UART_SendLine("Current Mode: Enter service safe mode");
    HAL_UART_SendLine("----------------------------------");

    HAL_UART_SendLine("Step 1: Backup current firmware to Secure External Flash");
    BackupManager_BackupCurrentFirmware(current_firmware_v1.name, current_firmware_v1.version);
    vTaskDelay(pdMS_TO_TICKS(300));

    HAL_UART_SendLine("Step 2: Download signed firmware package from cloud");
    HAL_UART_SendLine("Cloud Package: SW_APP_V2_ANTI_HACK");
    HAL_UART_SendLine("Secure Channel: TLS");
    vTaskDelay(pdMS_TO_TICKS(300));

    HAL_UART_SendLine("Step 3: Install candidate firmware image");
    HAL_UART_SendLine("Install Target: Internal Flash Candidate Slot");
    vTaskDelay(pdMS_TO_TICKS(300));

    HAL_UART_SendLine("Step 4: Secure Boot verification");
    bool secure_boot_passed = SecureBoot_Manager_VerifyFotaImage(
        cloud_firmware_v2.hash,
        installed_firmware_v2.hash,
        installed_firmware_v2.version,
        active_version
    );

    if (secure_boot_passed == false)
    {
        HAL_UART_SendLine("FOTA RESULT: FAILED");
        HAL_UART_SendLine("Action: Keep running old trusted firmware");
        BackupManager_RollbackToBackup();
        return;
    }

    active_app = SW_APP_V2_ANTI_HACK;
    active_version = installed_firmware_v2.version;

    HAL_UART_SendLine("----------------------------------");
    HAL_UART_SendLine("FOTA RESULT: SUCCESS");
    HAL_UART_SendLine("New SW Application Installed: SW_APP_V2_ANTI_HACK");
    HAL_UART_SendLine("Anti-Hack Protection: ENABLED");
    HAL_UART_SendLine("Security Rule: Reject switch double-press < 20 ms");
    HAL_UART_SendLine("----------------------------------");
}

bool FOTA_Manager_IsAntiHackAppActive(void)
{
    return active_app == SW_APP_V2_ANTI_HACK;
}

const char *FOTA_Manager_GetActiveAppName(void)
{
    if (active_app == SW_APP_V2_ANTI_HACK)
    {
        return "SW_APP_V2_ANTI_HACK";
    }

    return "SW_APP_V1_BASIC";
}