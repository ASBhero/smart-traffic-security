#ifndef SECURE_BOOT_MANAGER_H
#define SECURE_BOOT_MANAGER_H

#include <stdbool.h>
#include <stdint.h>

void SecureBoot_Manager_Init(void);

bool SecureBoot_Manager_VerifyFotaImage(
    const char *cloud_signed_hash,
    const char *installed_image_hash,
    uint32_t incoming_version,
    uint32_t current_version
);

#endif