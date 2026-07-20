
idf_component_register(
    SRCS
        "main.c"
        "hal_uart.c"
        "hal_gpio.c"
        "Traffic_sm.c"
        "fota_manager.c"
        "secure_boot_manager.c"
        "backup_manager.c"
    INCLUDE_DIRS
        "."
)