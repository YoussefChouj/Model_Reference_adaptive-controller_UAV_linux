Write-Output "=== ALL COM ports in Windows registry ==="
Get-ChildItem 'HKLM:\HARDWARE\DEVICEMAP\SERIALCOMM' -ErrorAction SilentlyContinue |
    ForEach-Object {
        $port = $_.Property[0]
        Write-Output "  Port: $port"
    }

Write-Output "`n=== All USB serial-class devices ==="
Get-WmiObject Win32_SerialPort -ErrorAction SilentlyContinue |
    Format-Table Name, DeviceID, Description, Status -AutoSize