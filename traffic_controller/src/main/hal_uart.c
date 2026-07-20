#include "hal_uart.h"

#include <stdio.h>

void HAL_UART_Init(void)
{
    printf("HAL_UART_Init: UART abstraction initialized\r\n");
    fflush(stdout);
}

void HAL_UART_SendString(const char *msg)
{
    if (msg == NULL)
    {
        return;
    }

    printf("%s", msg);
    fflush(stdout);
}

void HAL_UART_SendLine(const char *msg)
{
    if (msg == NULL)
    {
        return;
    }

    printf("%s\r\n", msg);
    fflush(stdout);
}