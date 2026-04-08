Motor diagram README

Files:
- `motor_pin_map.svg` ¡ª simple schematic-style top-down diagram showing motor positions, rotation direction, and mapped MCU pins.

How to produce a PNG (two common methods on Windows):

1) Inkscape (recommended, preserves vector quality)
- Install Inkscape: https://inkscape.org
- Convert to PNG from PowerShell:

```powershell
# Export at 1200x900 (same as SVG viewBox)
"C:\Program Files\Inkscape\bin\inkscape.com" -w 1200 -h 900 -o NOTE\diagrams\motor_pin_map.png NOTE\diagrams\motor_pin_map.svg
```

2) ImageMagick (magick)
- Install ImageMagick and ensure `magick` is in PATH.
- Convert in PowerShell:

```powershell
magick convert NOTE\diagrams\motor_pin_map.svg NOTE\diagrams\motor_pin_map.png
```

Notes and safety
- Before powering motors, remove propellers and set motors to `Set_Zero_Motors()` or `Set_IDLE_Motors()` in firmware.
- Verify wiring and ESC calibration for motor direction; swap motor wires or update rotation in firmware/mapping if needed.

If you want, I can:
- Generate the PNG for you here if the environment had ImageMagick or Inkscape available; currently I created the SVG and gave conversion commands for your Windows machine.
- Produce a higher-resolution SVG or add connector labels for ESC signal/ground/5V mapping.
- Add this diagram into `UAV_TUTORIAL.md` or `NOTE/README.md` for the tutorial.
