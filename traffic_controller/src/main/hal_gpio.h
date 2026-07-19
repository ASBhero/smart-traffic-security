#ifndef HAL_GPIO_H
#define HAL_GPIO_H

#include <stdbool.h>

void HAL_GPIO_Init(void);

void HAL_GPIO_ShowAllRed(void);

void HAL_GPIO_ShowNorthGreen(void);
void HAL_GPIO_ShowSouthGreen(void);
void HAL_GPIO_ShowEastGreen(void);
void HAL_GPIO_ShowWestGreen(void);

void HAL_GPIO_ShowPedestrianCrossing(void);
void HAL_GPIO_ShowServiceSafeMode(void);
void HAL_GPIO_ShowEmergencyNorthOnly(void);

bool HAL_GPIO_IsNorthSwitchPressed(void);
bool HAL_GPIO_IsSouthSwitchPressed(void);
bool HAL_GPIO_IsEastSwitchPressed(void);
bool HAL_GPIO_IsWestSwitchPressed(void);

bool HAL_GPIO_IsPedestrianRequested(void);
bool HAL_GPIO_IsServiceSwitchActivated(void);
bool HAL_GPIO_IsNorthEmergencySwitchPressed(void);

#endif