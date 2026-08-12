#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_linux_toolchain.sh
# One-time setup for the Linux ARM Cortex-M firmware toolchain.
# Run once on a fresh clone or after an OS reinstall.
#
# Prerequisites:
#   - sudo (for apt install and udev rules)
#   - The pyOCD udev rules need reloading after install
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
echo "[1/5] Installing system packages..."
packages=(
    gcc-arm-none-eabi
    binutils-arm-none-eabi
    gdb-multiarch
    openocd
    libusb-1.0-0-dev
)
# shellcheck disable=SC2086
sudo apt-get update -qq
sudo apt-get install -y -qq ${packages[*]}
echo "  ✓ System packages installed"
echo

# ---------------------------------------------------------------------------
# 2. Verify toolchain
# ---------------------------------------------------------------------------
echo "[2/5] Verifying arm-none-eabi-gcc..."
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
echo "[3/5] Installing pyOCD udev rules (allows non-root CMSIS-DAP access)..."
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
echo "[4/5] Checking plugdev group..."
if groups | grep -q '\bplugdev\b'; then
    echo "  ✓ User is in plugdev group"
else
    echo "  ⚠ User is NOT in plugdev group — run:"
    echo "    sudo usermod -aG plugdev ${USER}"
    echo "  Then log out and back in."
fi
echo

# ---------------------------------------------------------------------------
# 5. pyOCD probe list
# ---------------------------------------------------------------------------
echo "[5/5] Probing for CMSIS-DAP devices..."
if command -v pyocd &>/dev/null; then
    pyocd list 2>/dev/null || true
elif [[ -x "${VENV_PYTHON}" ]]; then
    "${VENV_PYTHON}" -m pyocd list 2>/dev/null || true
else
    echo "  ⚠ pyOCD not installed — install with:"
    echo "    ${VENV_PYTHON} -m pip install pyocd"
fi
echo

echo "=== Setup complete ==="
echo
echo "Build firmware:    cmake -B firmware/build -S firmware"
echo "                   cmake --build firmware/build"
echo "Flash firmware:   tasks.py flash"
echo "Probe info:       tasks.py probe-info"
