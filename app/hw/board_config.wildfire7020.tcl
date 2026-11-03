# Generated from manufacturer Hello World BD. Retain vendor DDR timing.
# PS initialization + UART verified on hardware, 2026-09-30.
# Part/revision below follow supplied schematic, not chip-marking inspection.
set board_verified 1
set board_part "xc7z020clg400-2"
set board_revision "Reference: EBF410020 V1R2 / EBF410021 V1.1"
set board_source "Vendor 7020 Hello World + EBF410020_SCH_20250307"
set ps7_properties [dict create]
dict set ps7_properties CONFIG.PCW_ACT_APU_PERIPHERAL_FREQMHZ {666.666687}
dict set ps7_properties CONFIG.PCW_ACT_CAN0_PERIPHERAL_FREQMHZ {23.8095}
dict set ps7_properties CONFIG.PCW_ACT_CAN1_PERIPHERAL_FREQMHZ {23.8095}
dict set ps7_properties CONFIG.PCW_ACT_CAN_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_DCI_PERIPHERAL_FREQMHZ {10.158730}
dict set ps7_properties CONFIG.PCW_ACT_ENET0_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_ENET1_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_FPGA1_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_FPGA2_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_FPGA3_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_I2C_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_ACT_PCAP_PERIPHERAL_FREQMHZ {200.000000}
dict set ps7_properties CONFIG.PCW_ACT_QSPI_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_SDIO_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_SMC_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_SPI_PERIPHERAL_FREQMHZ {10.000000}
dict set ps7_properties CONFIG.PCW_ACT_TPIU_PERIPHERAL_FREQMHZ {200.000000}
dict set ps7_properties CONFIG.PCW_ACT_TTC0_CLK0_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC0_CLK1_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC0_CLK2_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC1_CLK0_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC1_CLK1_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC1_CLK2_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_ACT_TTC_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_ACT_UART_PERIPHERAL_FREQMHZ {100.000000}
dict set ps7_properties CONFIG.PCW_ACT_USB0_PERIPHERAL_FREQMHZ {60}
dict set ps7_properties CONFIG.PCW_ACT_USB1_PERIPHERAL_FREQMHZ {60}
dict set ps7_properties CONFIG.PCW_ACT_WDT_PERIPHERAL_FREQMHZ {111.111115}
dict set ps7_properties CONFIG.PCW_APU_CLK_RATIO_ENABLE {6:2:1}
dict set ps7_properties CONFIG.PCW_APU_PERIPHERAL_FREQMHZ {666.666666}
dict set ps7_properties CONFIG.PCW_CAN0_PERIPHERAL_CLKSRC {External}
dict set ps7_properties CONFIG.PCW_CAN0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_CAN1_PERIPHERAL_CLKSRC {External}
dict set ps7_properties CONFIG.PCW_CAN1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_CAN_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_CAN_PERIPHERAL_VALID {0}
dict set ps7_properties CONFIG.PCW_CLK0_FREQ {10000000}
dict set ps7_properties CONFIG.PCW_CLK1_FREQ {10000000}
dict set ps7_properties CONFIG.PCW_CLK2_FREQ {10000000}
dict set ps7_properties CONFIG.PCW_CLK3_FREQ {10000000}
dict set ps7_properties CONFIG.PCW_CPU_CPU_6X4X_MAX_RANGE {667}
dict set ps7_properties CONFIG.PCW_CPU_PERIPHERAL_CLKSRC {ARM PLL}
dict set ps7_properties CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ {33.333333}
dict set ps7_properties CONFIG.PCW_DCI_PERIPHERAL_CLKSRC {DDR PLL}
dict set ps7_properties CONFIG.PCW_DCI_PERIPHERAL_FREQMHZ {10.159}
dict set ps7_properties CONFIG.PCW_DDR_PERIPHERAL_CLKSRC {DDR PLL}
dict set ps7_properties CONFIG.PCW_DDR_RAM_BASEADDR {0x00100000}
dict set ps7_properties CONFIG.PCW_DDR_RAM_HIGHADDR {0x3FFFFFFF}
dict set ps7_properties CONFIG.PCW_DM_WIDTH {4}
dict set ps7_properties CONFIG.PCW_DQS_WIDTH {4}
dict set ps7_properties CONFIG.PCW_DQ_WIDTH {32}
dict set ps7_properties CONFIG.PCW_ENET0_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_ENET0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_ENET1_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_ENET1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_ENET_RESET_POLARITY {Active Low}
dict set ps7_properties CONFIG.PCW_EN_4K_TIMER {0}
dict set ps7_properties CONFIG.PCW_EN_CAN0 {0}
dict set ps7_properties CONFIG.PCW_EN_CAN1 {0}
dict set ps7_properties CONFIG.PCW_EN_CLK0_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLK1_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLK2_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLK3_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLKTRIG0_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLKTRIG1_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLKTRIG2_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_CLKTRIG3_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_DDR {1}
dict set ps7_properties CONFIG.PCW_EN_EMIO_CAN0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_CAN1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_CD_SDIO0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_CD_SDIO1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_ENET0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_ENET1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_GPIO {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_I2C0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_I2C1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_MODEM_UART0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_MODEM_UART1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_PJTAG {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_SDIO0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_SDIO1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_SPI0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_SPI1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_SRAM_INT {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_TRACE {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_TTC0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_TTC1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_UART0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_UART1 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_WDT {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_WP_SDIO0 {0}
dict set ps7_properties CONFIG.PCW_EN_EMIO_WP_SDIO1 {0}
dict set ps7_properties CONFIG.PCW_EN_ENET0 {0}
dict set ps7_properties CONFIG.PCW_EN_ENET1 {0}
dict set ps7_properties CONFIG.PCW_EN_GPIO {0}
dict set ps7_properties CONFIG.PCW_EN_I2C0 {0}
dict set ps7_properties CONFIG.PCW_EN_I2C1 {0}
dict set ps7_properties CONFIG.PCW_EN_MODEM_UART0 {0}
dict set ps7_properties CONFIG.PCW_EN_MODEM_UART1 {0}
dict set ps7_properties CONFIG.PCW_EN_PJTAG {0}
dict set ps7_properties CONFIG.PCW_EN_PTP_ENET0 {0}
dict set ps7_properties CONFIG.PCW_EN_PTP_ENET1 {0}
dict set ps7_properties CONFIG.PCW_EN_QSPI {0}
dict set ps7_properties CONFIG.PCW_EN_RST0_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_RST1_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_RST2_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_RST3_PORT {0}
dict set ps7_properties CONFIG.PCW_EN_SDIO0 {0}
dict set ps7_properties CONFIG.PCW_EN_SDIO1 {0}
dict set ps7_properties CONFIG.PCW_EN_SMC {0}
dict set ps7_properties CONFIG.PCW_EN_SPI0 {0}
dict set ps7_properties CONFIG.PCW_EN_SPI1 {0}
dict set ps7_properties CONFIG.PCW_EN_TRACE {0}
dict set ps7_properties CONFIG.PCW_EN_TTC0 {0}
dict set ps7_properties CONFIG.PCW_EN_TTC1 {0}
dict set ps7_properties CONFIG.PCW_EN_UART0 {1}
dict set ps7_properties CONFIG.PCW_EN_UART1 {0}
dict set ps7_properties CONFIG.PCW_EN_USB0 {0}
dict set ps7_properties CONFIG.PCW_EN_USB1 {0}
dict set ps7_properties CONFIG.PCW_EN_WDT {0}
dict set ps7_properties CONFIG.PCW_FCLK0_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_FCLK1_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_FCLK2_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_FCLK3_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_FPGA1_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_FPGA2_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_FPGA3_PERIPHERAL_FREQMHZ {50}
dict set ps7_properties CONFIG.PCW_GP0_EN_MODIFIABLE_TXN {1}
dict set ps7_properties CONFIG.PCW_GP0_NUM_READ_THREADS {4}
dict set ps7_properties CONFIG.PCW_GP0_NUM_WRITE_THREADS {4}
dict set ps7_properties CONFIG.PCW_GP1_EN_MODIFIABLE_TXN {1}
dict set ps7_properties CONFIG.PCW_GP1_NUM_READ_THREADS {4}
dict set ps7_properties CONFIG.PCW_GP1_NUM_WRITE_THREADS {4}
dict set ps7_properties CONFIG.PCW_GPIO_EMIO_GPIO_ENABLE {0}
dict set ps7_properties CONFIG.PCW_GPIO_MIO_GPIO_ENABLE {0}
dict set ps7_properties CONFIG.PCW_GPIO_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_I2C0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_I2C1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_I2C_RESET_POLARITY {Active Low}
dict set ps7_properties CONFIG.PCW_IMPORT_BOARD_PRESET {None}
dict set ps7_properties CONFIG.PCW_INCLUDE_ACP_TRANS_CHECK {0}
dict set ps7_properties CONFIG.PCW_MIO_14_IOTYPE {LVCMOS 3.3V}
dict set ps7_properties CONFIG.PCW_MIO_14_PULLUP {enabled}
dict set ps7_properties CONFIG.PCW_MIO_14_SLEW {slow}
dict set ps7_properties CONFIG.PCW_MIO_15_IOTYPE {LVCMOS 3.3V}
dict set ps7_properties CONFIG.PCW_MIO_15_PULLUP {enabled}
dict set ps7_properties CONFIG.PCW_MIO_15_SLEW {slow}
dict set ps7_properties CONFIG.PCW_MIO_PRIMITIVE {54}
dict set ps7_properties CONFIG.PCW_MIO_TREE_PERIPHERALS {unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#UART 0#UART 0#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned}
dict set ps7_properties CONFIG.PCW_MIO_TREE_SIGNALS {unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#rx#tx#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned#unassigned}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_AR {1}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_CLR {1}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_RC {11}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_REA {1}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_RR {1}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_WC {11}
dict set ps7_properties CONFIG.PCW_NAND_CYCLES_T_WP {1}
dict set ps7_properties CONFIG.PCW_NAND_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_CEOE {1}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_PC {1}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_RC {11}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_TR {1}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_WC {11}
dict set ps7_properties CONFIG.PCW_NOR_CS0_T_WP {1}
dict set ps7_properties CONFIG.PCW_NOR_CS0_WE_TIME {0}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_CEOE {1}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_PC {1}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_RC {11}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_TR {1}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_WC {11}
dict set ps7_properties CONFIG.PCW_NOR_CS1_T_WP {1}
dict set ps7_properties CONFIG.PCW_NOR_CS1_WE_TIME {0}
dict set ps7_properties CONFIG.PCW_NOR_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_CEOE {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_PC {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_RC {11}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_TR {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_WC {11}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_T_WP {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS0_WE_TIME {0}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_CEOE {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_PC {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_RC {11}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_TR {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_WC {11}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_T_WP {1}
dict set ps7_properties CONFIG.PCW_NOR_SRAM_CS1_WE_TIME {0}
dict set ps7_properties CONFIG.PCW_OVERRIDE_BASIC_CLOCK {0}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_BOARD_DELAY0 {0.080}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_BOARD_DELAY1 {0.063}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_BOARD_DELAY2 {0.057}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_BOARD_DELAY3 {0.068}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_DQS_TO_CLK_DELAY_0 {-0.047}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_DQS_TO_CLK_DELAY_1 {-0.025}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_DQS_TO_CLK_DELAY_2 {-0.006}
dict set ps7_properties CONFIG.PCW_PACKAGE_DDR_DQS_TO_CLK_DELAY_3 {-0.017}
dict set ps7_properties CONFIG.PCW_PACKAGE_NAME {clg400}
dict set ps7_properties CONFIG.PCW_PCAP_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_PCAP_PERIPHERAL_FREQMHZ {200}
dict set ps7_properties CONFIG.PCW_PERIPHERAL_BOARD_PRESET {None}
dict set ps7_properties CONFIG.PCW_PJTAG_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_PLL_BYPASSMODE_ENABLE {0}
dict set ps7_properties CONFIG.PCW_PRESET_BANK0_VOLTAGE {LVCMOS 3.3V}
dict set ps7_properties CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 3.3V}
dict set ps7_properties CONFIG.PCW_PS7_SI_REV {PRODUCTION}
dict set ps7_properties CONFIG.PCW_QSPI_INTERNAL_HIGHADDRESS {0xFCFFFFFF}
dict set ps7_properties CONFIG.PCW_QSPI_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_QSPI_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_SD0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_SD1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_SDIO_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_SDIO_PERIPHERAL_VALID {0}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T0 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T1 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T2 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T3 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T4 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T5 {NA}
dict set ps7_properties CONFIG.PCW_SMC_CYCLE_T6 {NA}
dict set ps7_properties CONFIG.PCW_SMC_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_SMC_PERIPHERAL_VALID {0}
dict set ps7_properties CONFIG.PCW_SPI0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_SPI1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_SPI_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_SPI_PERIPHERAL_VALID {0}
dict set ps7_properties CONFIG.PCW_TPIU_PERIPHERAL_CLKSRC {External}
dict set ps7_properties CONFIG.PCW_TRACE_INTERNAL_WIDTH {2}
dict set ps7_properties CONFIG.PCW_TRACE_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_TTC0_CLK0_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC0_CLK0_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC0_CLK1_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC0_CLK1_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC0_CLK2_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC0_CLK2_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_TTC1_CLK0_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC1_CLK0_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC1_CLK1_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC1_CLK1_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC1_CLK2_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_TTC1_CLK2_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_TTC1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_UART0_BASEADDR {0xE0000000}
dict set ps7_properties CONFIG.PCW_UART0_BAUD_RATE {115200}
dict set ps7_properties CONFIG.PCW_UART0_GRP_FULL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_UART0_HIGHADDR {0xE0000FFF}
dict set ps7_properties CONFIG.PCW_UART0_PERIPHERAL_ENABLE {1}
dict set ps7_properties CONFIG.PCW_UART0_UART0_IO {MIO 14 .. 15}
dict set ps7_properties CONFIG.PCW_UART1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_UART_PERIPHERAL_CLKSRC {IO PLL}
dict set ps7_properties CONFIG.PCW_UART_PERIPHERAL_FREQMHZ {100}
dict set ps7_properties CONFIG.PCW_UART_PERIPHERAL_VALID {1}
dict set ps7_properties CONFIG.PCW_UIPARAM_ACT_DDR_FREQ_MHZ {533.333374}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_ADV_ENABLE {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_AL {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BL {8}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY0 {0.25}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY1 {0.25}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY2 {0.25}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BOARD_DELAY3 {0.25}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_0_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_0_PACKAGE_LENGTH {54.563}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_0_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_1_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_1_PACKAGE_LENGTH {54.563}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_1_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_2_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_2_PACKAGE_LENGTH {54.563}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_2_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_3_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_3_PACKAGE_LENGTH {54.563}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_3_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_CLOCK_STOP_EN {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_0_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_0_PACKAGE_LENGTH {101.239}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_0_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_1_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_1_PACKAGE_LENGTH {79.5025}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_1_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_2_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_2_PACKAGE_LENGTH {60.536}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_2_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_3_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_3_PACKAGE_LENGTH {71.7715}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_3_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_0 {0.0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_1 {0.0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_2 {0.0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQS_TO_CLK_DELAY_3 {0.0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_0_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_0_PACKAGE_LENGTH {104.5365}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_0_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_1_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_1_PACKAGE_LENGTH {70.676}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_1_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_2_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_2_PACKAGE_LENGTH {59.1615}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_2_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_3_LENGTH_MM {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_3_PACKAGE_LENGTH {81.319}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_DQ_3_PROPOGATION_DELAY {160}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_ENABLE {1}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_FREQ_MHZ {533.333333}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_HIGH_TEMP {Normal (0-85)}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_MEMORY_TYPE {DDR 3}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K256M16 RE-125}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_TRAIN_DATA_EYE {1}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_TRAIN_READ_GATE {1}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_TRAIN_WRITE_LEVEL {1}
dict set ps7_properties CONFIG.PCW_UIPARAM_DDR_USE_INTERNAL_VREF {0}
dict set ps7_properties CONFIG.PCW_UIPARAM_GENERATE_SUMMARY {NA}
dict set ps7_properties CONFIG.PCW_USB0_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_USB1_PERIPHERAL_ENABLE {0}
dict set ps7_properties CONFIG.PCW_USB_RESET_POLARITY {Active Low}
dict set ps7_properties CONFIG.PCW_USE_AXI_FABRIC_IDLE {0}
dict set ps7_properties CONFIG.PCW_USE_AXI_NONSECURE {0}
dict set ps7_properties CONFIG.PCW_USE_CORESIGHT {0}
dict set ps7_properties CONFIG.PCW_USE_CROSS_TRIGGER {0}
dict set ps7_properties CONFIG.PCW_USE_CR_FABRIC {1}
dict set ps7_properties CONFIG.PCW_USE_DDR_BYPASS {0}
dict set ps7_properties CONFIG.PCW_USE_DEBUG {0}
dict set ps7_properties CONFIG.PCW_USE_DMA0 {0}
dict set ps7_properties CONFIG.PCW_USE_DMA1 {0}
dict set ps7_properties CONFIG.PCW_USE_DMA2 {0}
dict set ps7_properties CONFIG.PCW_USE_DMA3 {0}
dict set ps7_properties CONFIG.PCW_USE_EXPANDED_IOP {0}
dict set ps7_properties CONFIG.PCW_USE_FABRIC_INTERRUPT {0}
dict set ps7_properties CONFIG.PCW_USE_HIGH_OCM {0}
dict set ps7_properties CONFIG.PCW_USE_M_AXI_GP0 {0}
dict set ps7_properties CONFIG.PCW_USE_M_AXI_GP1 {0}
dict set ps7_properties CONFIG.PCW_USE_PROC_EVENT_BUS {0}
dict set ps7_properties CONFIG.PCW_USE_PS_SLCR_REGISTERS {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_ACP {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_GP0 {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_GP1 {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_HP0 {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_HP1 {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_HP2 {0}
dict set ps7_properties CONFIG.PCW_USE_S_AXI_HP3 {0}
dict set ps7_properties CONFIG.PCW_USE_TRACE {0}
dict set ps7_properties CONFIG.PCW_VALUE_SILVERSION {3}
dict set ps7_properties CONFIG.PCW_WDT_PERIPHERAL_CLKSRC {CPU_1X}
dict set ps7_properties CONFIG.PCW_WDT_PERIPHERAL_DIVISOR0 {1}
dict set ps7_properties CONFIG.PCW_WDT_PERIPHERAL_ENABLE {0}
