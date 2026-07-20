#include "backup_manager.h"

#include <stdio.h>
#include <string.h>

#include "hal_uart.h"

#define BACKUP_NAME_SIZE 64

static char backup_firmware_name[BACKUP_NAME_SIZE] = "NO_BACKUP";
static uint32_t backup_firmware_version = 0U;

void BackupManager_Init(void)
{
    memset(backup_firmware_name, 0, sizeof(backup_firmware_name));
    snprintf(backup_firmware_name, sizeof(backup_firmware_name), "NO_BACKUP");

    backup_firmware_version = 0U;

    HAL_UART_SendLine("Backup Manager Initialized");
    HAL_UART_SendLine("Secure External Flash: Ready for backup / rollback storage");
}

void BackupManager_BackupCurrentFirmware(const char *firmware_name, uint32_t version)
{
    if (firmware_name == NULL)
    {
        return;
    }

    snprintf(backup_firmware_name, sizeof(backup_firmware_name), "%s", firmware_name);
    backup_firmware_version = version;

    HAL_UART_SendLine("----------------------------------");
    HAL_UART_SendLine("Secure External Flash: Backup started");
    HAL_UART_SendString("Backup Firmware Name: ");
    HAL_UART_SendLine(backup_firmware_name);

    char msg[80];
    snprintf(msg, sizeof(msg), "Backup Firmware Version: %lu", (unsigned long)backup_firmware_version);
    HAL_UART_SendLine(msg);

    HAL_UART_SendLine("Backup stored successfully");
    HAL_UART_SendLine("----------------------------------");
}

void BackupManager_RollbackToBackup(void)
{
    HAL_UART_SendLine("----------------------------------");
    HAL_UART_SendLine("ROLLBACK STARTED");
    HAL_UART_SendLine("Reason: New firmware failed secure boot verification");
    HAL_UART_SendString("Restoring backup firmware from Secure External Flash: ");
    HAL_UART_SendLine(backup_firmware_name);
    HAL_UART_SendLine("Rollback completed");
    HAL_UART_SendLine("----------------------------------");
}

const char *BackupManager_GetBackupFirmwareName(void)
{
    return backup_firmware_name;
}

uint32_t BackupManager_GetBackupFirmwareVersion(void)
{
    return backup_firmware_version;
}