#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_linux_toolchain.sh
# One-time setup for the Linux ARM Cortex-M firmware toolchain.
# Run once on a fresh clone or after an OS reinstall.
#
# Prerequisites:
#   - sudo (for apt install and udev rules)
#   - The pyOCD udev rules need reloading after install
#
# What this script does (per session 2026-08-16 wireless-bridge fix):
#   1. apt packages including openocd (backup tool) and stm32flash
#   2. arm-none-eabi-gcc sanity check
#   3. pyOCD udev rules
#   4. plugdev group membership
#   5. CMSIS Pack install: stm32f407 — required; cortex_m fallback no-ops
#   6. hid_mcp2200 blacklist — required for ATK-HS-V3-CMSIS-DAP writes
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
PYOCD_UDev_DIR="${REPO_ROOT}/.venv/lib/python3.12/site-packages/pyocd/udev"

echo "=== Linux ARM toolchain setup ==="
echo

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
echo "[1/6] Installing system packages..."
packages=(
    gcc-arm-none-eabi
    binutils-arm-none-eabi
    gdb-multiarch
    libusb-1.0-0-dev
)
# openocd + stm32flash are alternative flashing tools (wireless bridge
# fallback path; included for completeness). Only install if user agrees —
# they're large and not required for the pyocd path.
if [[ "${INSTALL_OPENOCD:-1}" -eq 1 ]]; then
    packages+=(openocd)
fi
if [[ "${INSTALL_STM32FLASH:-0}" -eq 1 ]]; then
    packages+=(stm32flash)
fi
# shellcheck disable=SC2086
sudo apt-get update -qq
sudo apt-get install -y -qq ${packages[*]}
echo "  ✓ System packages installed"
echo

# ---------------------------------------------------------------------------
# 2. Verify toolchain
# ---------------------------------------------------------------------------
echo "[2/6] Verifying arm-none-eabi-gcc..."
if command -v arm-none-eabi-gcc &>/dev/null; then
    arm-none-eabi-gcc --version | head -1
    echo "  ✓ arm-none-eabi-gcc found"
else
    echo "  ✗ arm-none-eabi-gcc NOT FOUND — check apt install output above"
    exit 1
fi
echo

# ---------------------------------------------------------------------------
# 3. pyOCD udev rules
# ---------------------------------------------------------------------------
echo "[3/6] Installing pyOCD udev rules (allows non-root CMSIS-DAP access)..."
if [[ -d "${PYOCD_UDev_DIR}" ]]; then
    sudo cp "${PYOCD_UDev_DIR}"/*.rules /etc/udev/rules.d/ 2>/dev/null || true
    echo "  ✓ udev rules copied from pyOCD package"
else
    echo "  ⚠ pyOCD udev rules not found — install pyOCD first:"
    echo "    ${VENV_PYTHON} -m pip install pyocd"
    echo "  Then re-run this script."
fi
sudo udevadm control --reload
sudo udevadm trigger
echo "  ✓ udev rules reloaded"
echo

# ---------------------------------------------------------------------------
# 4. User groups
# ---------------------------------------------------------------------------
echo "[4/6] Checking plugdev group..."
if groups | grep -q '\bplugdev\b'; then
    echo "  ✓ User is in plugdev group"
else
    echo "  ⚠ User is NOT in plugdev group — run:"
    echo "    sudo usermod -aG plugdev ${USER}"
    echo "  Then log out and back in."
fi
echo

# ---------------------------------------------------------------------------
# 5. CMSIS Pack — STM32F4xx_DFP
# ---------------------------------------------------------------------------
# pyocd's cortex_m fallback target silently no-ops on flash. The chip-specific
# target (stm32f407zgtx) from the STM32F4xx_DFP pack provides a real flash
# algorithm. Without this, `tasks.py flash` exits 0 but flash is unchanged.
# See docs/adr/0015-bridge-flash-pipeline-linux.md.
echo "[5/6] Installing STM32F4xx DFP pack for pyocd..."
if [[ -x "${VENV_PYTHON}" ]]; then
    "${VENV_PYTHON}" -m pyocd pack update || true
    "${VENV_PYTHON}" -m pyocd pack install stm32f407 || true
    if "${VENV_PYTHON}" -m pyocd list --targets 2>/dev/null | grep -q stm32f407; then
        echo "  ✓ stm32f407 target installed"
    else
        echo "  ⚠ stm32f407 target NOT installed. Re-run with internet access."
    fi
else
    echo "  ⚠ venv not found — skipping DFP install"
fi
echo

# ---------------------------------------------------------------------------
# 6. hid_mcp2200 blacklist
# ---------------------------------------------------------------------------
# The ATK-HS-V3-CMSIS-DAP (Microchip 04d8:00df) is a composite CDC-ACM + HID
# device. Linux's hid_mcp2200 driver claims the HID interface by a misleading
# PID heuristic, so on a default kernel the bridge's CMSIS-DAP writes silently
# drop. install /bin/false prevents the claim; replug the bridge to apply.
# Source: docs/adr/0015-bridge-flash-pipeline-linux.md.
echo "[6/6] Blacklisting hid_mcp2200..."
CONF_REPO="${REPO_ROOT}/etc-modprobe-d/blacklist-hid-mcp2200.conf"
CONF_ETC="/etc/modprobe.d/blacklist-hid-mcp2200.conf"
if [[ -f "${CONF_REPO}" ]]; then
    sudo install -m 644 "${CONF_REPO}" "${CONF_ETC}"
    sudo modprobe -r hid_mcp2200 2>/dev/null || true
    echo "  ✓ Installed ${CONF_ETC}; removed current hid_mcp2200 binding (replug the bridge)"
else
    echo "  ⚠ Repo copy of blacklist missing — skip; see ${CONF_REPO}"
fi
echo

echo "=== Setup complete ==="
echo
echo "Build firmware:    ${VENV_PYTHON} tasks.py build"
echo "Flash firmware:    ${VENV_PYTHON} tasks.py flash"
echo "Probe info:        ${VENV_PYTHON} tasks.py probe-info"
echo
echo "If your bridge was already plugged in, replug it now so the new"
echo "driver binding + DFP target take effect."
echo "Verify: cat /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1"
echo "        (should be DRIVER=hid-generic)"
echo "        ${VENV_PYTHON} -m pyocd list --targets | grep stm32f407"
