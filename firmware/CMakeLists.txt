cmake_minimum_required(VERSION 3.20)
project(JX_FLY C ASM)

# ------------------------------------------------------------------
# Target
# ------------------------------------------------------------------
set(TARGET_JX_FLY JX_FLY)

# Source tree: look in the parent directory (repo root).
# This mirrors the Keil .uvprojx layout without moving any files.
set(FW_ROOT ${CMAKE_SOURCE_DIR}/..)

# Collect C sources recursively, excluding test/harness/stub files
file(GLOB_RECURSE FW_SOURCES
    ${FW_ROOT}/API/*.c
    ${FW_ROOT}/BSP/*.c
    ${FW_ROOT}/TASK/*.c
    ${FW_ROOT}/USER/*.c
    ${FW_ROOT}/Global_file/*.c
    ${FW_ROOT}/stm32_lib/*.c
    ${FW_ROOT}/FreeRTOS/*.c
    # FreeRTOS GCC ARM_CM4F port (replaces Keil RVDS port)
    ${FW_ROOT}/FreeRTOS/portable/GCC/ARM_CM4F/port.c
    # newlib stubs (errno, etc.)
    ${CMAKE_SOURCE_DIR}/startup/newlib_stubs.c
)

# Exclude FreeRTOS heap implementations except heap_4 (matches Keil project)
foreach(heap heap_1 heap_2 heap_3 heap_5)
    list(FILTER FW_SOURCES EXCLUDE REGEX ".*/${heap}\\.c$")
endforeach()

# Exclude case-only symlinks placed to satisfy Keil's case-insensitive
# includes on a case-sensitive FS. Only the lowercase originals compile.
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/GlobalUse_Basic_Function\\.c$")
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/Global_Declare\\.c$")

# Exclude test/harness/stub files used by the off-target lane
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/tests/.*\\.c$")
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/stubs/.*\\.c$")
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/shim/.*\\.c$")
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/harness/.*\\.c$")
# Exclude all Keil RVDS ports — only the GCC ARM_CM4F port is used
list(FILTER FW_SOURCES EXCLUDE REGEX ".*portable/RVDS/.*\\.c$")
# Exclude demo_learning.c (experimental; defines main() colliding with main.c)
list(FILTER FW_SOURCES EXCLUDE REGEX ".*/demo_learning\\.c$")

# Exclude ST peripheral drivers not used by the F407ZG project.
# Filename-only match anchored to end of string with .*/ prefix.
foreach(driver
    stm32f4xx_fmc        # F407 uses FSMC, not FMC
    stm32f4xx_ltdc       # F407 has no LCD-TFT
    stm32f4xx_dcmi       # digital camera interface unused
    stm32f4xx_dac        # DAC unused
    stm32f4xx_dma2d      # DMA2D unused
    stm32f4xx_cryp
    stm32f4xx_cryp_aes
    stm32f4xx_cryp_des
    stm32f4xx_cryp_tdes
    stm32f4xx_hash
    stm32f4xx_hash_md5
    stm32f4xx_hash_sha1
    stm32f4xx_rng
    stm32f4xx_sai        # serial audio interface unused
    stm32f4xx_can        # CAN bus unused
    stm32f4xx_iwdg       # independent watchdog unused
    stm32f4xx_wwdg       # window watchdog unused
    stm32f4xx_rtc        # RTC unused
    stm32f4xx_dbgmcu     # debug MCU functions unused
)
    list(FILTER FW_SOURCES EXCLUDE REGEX ".*/${driver}\\.c$")
endforeach()

# Collect ASM sources — GNU AS (GAS) syntax startup only
file(GLOB_RECURSE FW_ASM_SOURCES
    ${CMAKE_SOURCE_DIR}/startup/*.s
)

# Exclude Keil RVDS port — replaced by GCC port above
list(FILTER FW_SOURCES EXCLUDE REGEX ".*portable/RVDS/ARM_CM4F/port\\.c$")

add_executable(${TARGET_JX_FLY}.elf
    ${FW_SOURCES}
    ${FW_ASM_SOURCES}
)

# ------------------------------------------------------------------
# Include paths
# ------------------------------------------------------------------
target_include_directories(${TARGET_JX_FLY}.elf PRIVATE
    ${FW_ROOT}
    ${FW_ROOT}/USER
    ${FW_ROOT}/stm32_lib
    ${FW_ROOT}/TASK
    ${FW_ROOT}/Global_file
    ${FW_ROOT}/BSP
    ${FW_ROOT}/API
    ${FW_ROOT}/FreeRTOS/include
    ${FW_ROOT}/FreeRTOS/portable/GCC/ARM_CM4F
    ${FW_ROOT}/FreeRTOS/portable/MemMang
)

# ------------------------------------------------------------------
# Preprocessor defines
# ------------------------------------------------------------------
target_compile_definitions(${TARGET_JX_FLY}.elf PRIVATE
    STM32F40_41xxx
    USE_STDPERIPH_DRIVER
)

# ------------------------------------------------------------------
# Compile options — match Keil ARMCC defaults + hardening
# ------------------------------------------------------------------
target_compile_options(${TARGET_JX_FLY}.elf PRIVATE
    # ISA
    -mcpu=cortex-m4 -mthumb
    -mfloat-abi=hard -mfpu=fpv4-sp-d16

    # Diagnostics
    -Wall -Wextra
    -Wno-unused-parameter

    # Optimisation
    -Og
    -fno-common

    # Sections
    -ffunction-sections -fdata-sections
)

# ------------------------------------------------------------------
# Linker options
# ------------------------------------------------------------------
target_link_options(${TARGET_JX_FLY}.elf PRIVATE
    -T${CMAKE_SOURCE_DIR}/cmake/stm32f407zg.ld

    # ISA
    -mcpu=cortex-m4 -mthumb
    -mfloat-abi=hard -mfpu=fpv4-sp-d16

    # Libraries — newlib nano + nosys. Specs belong here, not in compile opts.
    --specs=nano.specs --specs=nosys.specs
    -lc -lm -lnosys

    # Optimisation
    -Wl,--gc-sections
    -Wl,-Map=${TARGET_JX_FLY}.map
    -Wl,--print-memory-usage

    # Float printf
    -Wl,-u,_printf_float
)

# ------------------------------------------------------------------
# Output artifacts
# ------------------------------------------------------------------
add_custom_command(TARGET ${TARGET_JX_FLY}.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex -R .eeprom
        ${TARGET_JX_FLY}.elf ${TARGET_JX_FLY}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary -R .eeprom
        ${TARGET_JX_FLY}.elf ${TARGET_JX_FLY}.bin
    COMMAND ${CMAKE_SIZE} --format=berkeley ${TARGET_JX_FLY}.elf
    COMMENT "Building ${TARGET_JX_FLY}.hex and ${TARGET_JX_FLY}.bin"
)

# Install hex/bin alongside ELF
install(FILES
    ${CMAKE_CURRENT_BINARY_DIR}/${TARGET_JX_FLY}.hex
    ${CMAKE_CURRENT_BINARY_DIR}/${TARGET_JX_FLY}.bin
    DESTINATION bin
)

# Default build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()
