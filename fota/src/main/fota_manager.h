#ifndef FOTA_MANAGER_H
#define FOTA_MANAGER_H

#include <stdbool.h>

void FOTA_Manager_Init(void);
void FOTA_Manager_InstallNewApplication(void);

bool FOTA_Manager_IsAntiHackAppActive(void);
const char *FOTA_Manager_GetActiveAppName(void);

#endif