
#ifndef HAL_UART_H
#define HAL_UART_H

void HAL_UART_Init(void);
void HAL_UART_SendString(const char *msg);
void HAL_UART_SendLine(const char *msg);

#endif