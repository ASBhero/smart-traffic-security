#ifndef BACKUP_MANAGER_H
#define BACKUP_MANAGER_H

#include <stdint.h>

void BackupManager_Init(void);
void BackupManager_BackupCurrentFirmware(const char *firmware_name, uint32_t version);
void BackupManager_RollbackToBackup(void);

const char *BackupManager_GetBackupFirmwareName(void);
uint32_t BackupManager_GetBackupFirmwareVersion(void);

#endif