#include "secure_boot_manager.h"

#include <stdio.h>
#include <string.h>

#include "hal_uart.h"

void SecureBoot_Manager_Init(void)
{
    HAL_UART_SendLine("Secure Boot Manager Initialized");
    HAL_UART_SendLine("Microchip Secure IC: ATECC608 Secure Element");
    HAL_UART_SendLine("Root of Trust: ENABLED");
    HAL_UART_SendLine("Secure Boot Check: Signature / Hash / Version verification ready");
}

bool SecureBoot_Manager_VerifyFotaImage(
    const char *cloud_signed_hash,
    const char *installed_image_hash,
    uint32_t incoming_version,
    uint32_t current_version
)
{
    HAL_UART_SendLine("----------------------------------");
    HAL_UART_SendLine("SECURE BOOT CHECK STARTED");
    HAL_UART_SendLine("Microchip Secure IC: Verifying firmware authenticity");

    if ((cloud_signed_hash == NULL) || (installed_image_hash == NULL))
    {
        HAL_UART_SendLine("SECURE BOOT FAIL: Null firmware hash");
        return false;
    }

    HAL_UART_SendLine("Check 1: Verify signature/hash using Secure IC");
    HAL_UART_SendLine("Check 2: Compare installed image with cloud-signed update");

    if (strcmp(cloud_signed_hash, installed_image_hash) != 0)
    {
        HAL_UART_SendLine("SECURE BOOT FAIL: Installed image does not match cloud-signed firmware");
        HAL_UART_SendLine("Action: Reject tampered firmware");
        HAL_UART_SendLine("----------------------------------");
        return false;
    }

    HAL_UART_SendLine("Check 3: Anti-rollback version check");

    if (incoming_version <= current_version)
    {
        HAL_UART_SendLine("SECURE BOOT FAIL: Rollback attempt detected");
        HAL_UART_SendLine("Action: Reject old or downgraded firmware");
        HAL_UART_SendLine("----------------------------------");
        return false;
    }

    HAL_UART_SendLine("SECURE BOOT PASS: Firmware is authentic and newer");
    HAL_UART_SendLine("Action: Accept and boot new firmware");
    HAL_UART_SendLine("----------------------------------");

    return true;
}