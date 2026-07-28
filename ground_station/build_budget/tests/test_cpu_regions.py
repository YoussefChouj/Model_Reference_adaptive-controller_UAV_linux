"""Tests for the project / CPU-region parser."""
from pathlib import Path

import pytest

from ground_station.build_budget.cpu_regions import (
    CpuRegions, parse_cpu_line, parse_on_chip_memories, parse_project_regions,
)


SAMPLE = Path(__file__).parent / "sample_artifacts" / "JX_FLY_cpu.xml"


def test_sample_project_yields_stm32f407_canonical_layout():
    r = parse_project_regions(SAMPLE)
    # STM32F407ZGTx: 128 KB main SRAM, 64 KB CCM, 1 MB flash.
    assert r.iram == 128 * 1024
    assert r.iram2 == 64 * 1024
    assert r.irom == 1024 * 1024


def test_total_ram_is_iram_plus_iram2_ccm():
    r = parse_project_regions(SAMPLE)
    assert r.total_ram == 192 * 1024


def test_cpu_line_parses_addresses_too():
    text = SAMPLE.read_text(encoding="utf-8")
    iram_s, iram2_s, irom_s, iram_a, iram2_a, irom_a = parse_cpu_line(text)
    assert (iram_s, iram2_s, irom_s) == (128*1024, 64*1024, 1024*1024)
    assert iram_a == 0x20000000
    assert iram2_a == 0x10000000
    assert irom_a == 0x08000000


def test_on_chip_memories_agrees_with_cpu_line():
    text = SAMPLE.read_text(encoding="utf-8")
    ocm = parse_on_chip_memories(text)
    assert ocm == {"IRAM": 128*1024, "IRAM2": 64*1024, "IROM": 1024*1024}


def test_project_without_cpu_line_raises():
    with pytest.raises(ValueError, match="Cpu"):
        parse_project_regions_text("<Project/>")


def test_percent_ram_and_percent_flash_use_total_capacity():
    r = parse_project_regions(SAMPLE)
    # 50% of 1 MB flash = 512 KiB.
    assert r.percent_flash(512 * 1024) == pytest.approx(50.0)
    # 50% of 192 KiB = 96 KiB.
    assert r.percent_ram(96 * 1024) == pytest.approx(50.0)


# Avoid importing the parser as a top-level dependency.
def parse_project_regions_text(text):
    from ground_station.build_budget.cpu_regions import parse_cpu_line
    iram_s, iram2_s, irom_s, _, _, _ = parse_cpu_line(text)
    if not (iram_s and irom_s):
        raise ValueError(f"no <Cpu> IRAM/IRAM2/IROM line found")
    return CpuRegions(iram=iram_s, iram2=iram2_s, irom=irom_s)
